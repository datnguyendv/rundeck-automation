# import argparse
import sys
import os
from typing import Dict, Optional, List
from pathlib import Path

from utils import (
    setup_logger,
    AppConfig,
    VaultClient,
    GitClient,
    GitOperationError,
    TemplateRenderError,
    TemplateRenderer,
    VaultAPIError,
)

logger = setup_logger(__name__)


def get_rundeck_context() -> Dict[str, str]:
    context = {
        "title": f"{os.environ.get('RD_JOB_NAME')} for {os.getenv('RD_OPTION_VAULTNAME')}",
        "env": os.environ.get("RD_OPTION_ENV", "dev"),
        "job_id": os.getenv("RD_JOB_ID", "unknown_job"),
        "execution_uuid": os.getenv("RD_JOB_EXECUTIONUUID", "unknown_exec"),
        "exec_id": os.getenv("RD_JOB_EXECID", "0"),
        "user": os.getenv("RD_JOB_USERNAME", "system"),
        "vault_name": os.getenv("RD_OPTION_VAULTNAME"),
        "namespace": os.getenv("RD_OPTION_NAMESPACE", "default"),
        "action": "delete",  # Always 'delete' for this script
    }
    logger.info(f"Rundeck context: job_id={context['job_id']}, user={context['user']}")
    return context


def get_git_branch_from_env(env: str) -> str:
    """Map environment to git branch"""
    branch_mapping = {"dev": "ct-dev", "uat": "ct-uat", "prod": "ct-prod"}
    return branch_mapping.get(env.lower(), "ct-dev")


def generate_vault_gke_yaml_to_git(
    keys: List[str], context: Dict[str, str], config: AppConfig, template_dir: Path
) -> bool:
    if not config.git:
        logger.error("Git configuration not available")
        return False

    try:
        # Determine branch based on environment
        branch = get_git_branch_from_env(context["env"])
        logger.info(f"Using git branch: {branch} for environment: {context['env']}")

        # Setup local repo path
        repo_local_path = Path(
            f"{config.output_dir}/{context['job_id']}/config-repo-{context['exec_id']}"
        )

        # Initialize Git client
        git_client = GitClient(
            repo_url=config.git.repo_url,
            username=config.git.username,
            token=config.git.token,
        )

        # Clone the repository
        logger.info("=== STEP 1: Cloning Git Repository ===")
        git_client.clone(repo_local_path, branch=branch, depth=1)

        # Prepare template data
        template_data = {
            "ENV": context["env"],
            "vault_name": context["vault_name"],
            "namespace": context["namespace"],
            "action": context["action"],
            "vault_keys": keys,
        }

        # Generate YAML content
        logger.info("=== STEP 2: Generating YAML Content ===")
        renderer = TemplateRenderer(template_dir=template_dir)
        input_yaml_path = repo_local_path / "input.yaml"
        renderer.render_to_file("vault-gke.j2", template_data, input_yaml_path)

        logger.info(f"✅ YAML written to: {input_yaml_path}")

        # Commit and push changes
        logger.info("=== STEP 4: Committing and Pushing Changes ===")
        commit_message = (
            f"{context['title']} on {context['env']} - (Job: {context['job_id']}"
        )

        git_client.commit_and_push(
            repo_path=repo_local_path,
            file_path="input.yaml",
            commit_message=commit_message,
            branch=branch,
            author_name=config.git.username,
            author_email=config.git.author_email,
        )

        logger.info("✅ YAML generated and pushed to Git successfully")
        return True

    except (GitOperationError, TemplateRenderError) as e:
        logger.error(f"Git/Template operation failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in Git workflow: {e}")
        return False


def delete_vault_secret(
    vault_client: VaultClient, vault_path: str, permanent: bool = False
) -> Optional[List[str]]:
    try:
        logger.info("=" * 80)
        logger.info(f"🗑️  Deleting secret from Vault: {vault_path}")
        logger.info("=" * 80)

        # Step 1: Read existing keys before deletion (for logging/YAML)
        deleted_keys = []
        try:
            existing_data = vault_client.read_secret(vault_path)
            if existing_data:
                deleted_keys = list(existing_data.keys())
                logger.info(f"📋 Found {len(deleted_keys)} keys to delete")
                logger.info(f"Keys: {', '.join(deleted_keys)}")
        except VaultAPIError as e:
            if "404" in str(e).lower() or "not found" in str(e).lower():
                logger.warning("⚠️  Secret not found at specified path")
                return []
            else:
                raise

        # Step 2: Perform deletion
        if permanent and vault_client.kv_version == 2:
            logger.warning("🚨 PERMANENT DELETION MODE (KV v2 metadata)")
            success = vault_client.delete_metadata(vault_path)
        else:
            success = vault_client.delete_secret(vault_path)

        if success:
            logger.info("")
            logger.info("=" * 80)
            logger.info("✅ SECRET DELETION COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            logger.info(f"Vault path: {vault_path}")
            logger.info(f"Deleted keys: {len(deleted_keys)}")
            logger.info(
                f"Deletion type: {'PERMANENT (metadata)' if permanent else 'STANDARD'}"
            )
            logger.info("=" * 80)
            return deleted_keys
        else:
            logger.error("❌ Deletion failed")
            return None

    except VaultAPIError as e:
        logger.error(f"❌ Vault operation failed: {e}")
        return None
    except Exception as e:
        logger.exception(f"❌ Unexpected error: {e}")
        return None


def main() -> int:
    try:
        logger.info("=" * 80)
        logger.info("🗑️  Vault Secret Deletion Tool - Starting")
        logger.info("=" * 80)

        # Load configuration
        config = AppConfig.from_env()
        context = get_rundeck_context()

        # Determine vault path
        if not config.vault.path:
            logger.error(
                "❌ Vault path is required (set VAULT_PATH or use --vault-path)"
            )
            return 1

        # Validate token
        if not config.vault.token:
            logger.error(
                "❌ Vault token is required (set VAULT_TOKEN or RD_OPTION_VAULTTOKEN)"
            )
            return 1

        # Log configuration
        logger.info(f"Vault address: {config.vault.addr}")
        logger.info(f"Vault path: {config.vault.path}")
        # logger.info(f"KV version: {args.kv_version}")
        # logger.info(f"Permanent deletion: {args.permanent}")
        # logger.info(f"Generate YAML: {not args.no_yaml}")

        # Initialize Vault client
        vault_client = VaultClient(
            addr=config.vault.addr,
            token=config.vault.token,
            # kv_version=args.kv_version
        )

        # Perform deletion
        deleted_keys = delete_vault_secret(
            vault_client=vault_client,
            vault_path=config.vault.path,
            # permanent=args.permanent
        )

        if deleted_keys is None:
            logger.error("❌ Failed to delete vault secret")
            return 2

        if not deleted_keys:
            logger.warning("⚠️  No keys were deleted (secret may not exist)")
            # Still continue to YAML generation if requested

        # Generate YAML manifest (if not disabled)
        # if not args.no_yaml:
        template_dir = Path(config.template_dir)
        yaml_generated = generate_vault_gke_yaml_to_git(
            deleted_keys, context, config, template_dir
        )

        if yaml_generated:
            logger.info("✅ YAML manifest generated successfully")
        else:
            logger.warning("⚠️  YAML generation skipped or failed (non-critical)")

        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ OPERATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        return 0

    except VaultAPIError as e:
        logger.error(f"❌ Vault operation failed: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return 2

    except Exception as e:
        logger.exception(f"❌ Unexpected error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
