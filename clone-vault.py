import sys
import os
from typing import Dict, Any, Optional, List, Tuple
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
        "action": os.getenv("RD_OPTION_ACTION", "create"),
        "source_vault_path": f"gke/{os.getenv('RD_OPTION_SOURCEVAULTNAME')}",
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


def copy_vault_secret(
    vault_client: VaultClient, source_path: str, dest_path: str, overwrite: bool = False
) -> Optional[Tuple[Dict[str, Any], str]]:
    try:
        # Step 1: Read data from source vault
        logger.info("=" * 80)
        logger.info(f"📖 Reading secrets from SOURCE: {source_path}")
        logger.info("=" * 80)

        source_data = vault_client.read_secret(source_path)

        if not source_data:
            logger.warning("⚠️ Source vault exists but contains no data")
            return None

        logger.info(f"✅ Successfully read {len(source_data)} keys from source vault")
        logger.info(f"Keys: {', '.join(source_data.keys())}")

        # Step 2: Check if destination vault exists
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"📝 Writing secrets to DESTINATION: {dest_path}")
        logger.info("=" * 80)

        dest_exists = False
        existing_dest_data = {}

        try:
            existing_dest_data = vault_client.read_secret(dest_path)
            dest_exists = True
            logger.info(
                f"ℹ️ Destination vault exists with {len(existing_dest_data)} keys"
            )
        except VaultAPIError as e:
            if "404" in str(e).lower() or "not found" in str(e).lower():
                logger.info("ℹ️ Destination vault does not exist → will create new")
            else:
                raise

        # Step 3: Determine final data based on overwrite flag
        action = "create"  # Default action
        if overwrite or not dest_exists:
            final_data = source_data
            action = "create"
            logger.info(f"📝 Mode: {'OVERWRITE' if dest_exists else 'CREATE NEW'}")
        else:
            # Merge: source data takes precedence over existing destination data
            final_data = {**existing_dest_data, **source_data}
            action = "add"
            logger.info("📝 Mode: MERGE (source data takes precedence)")

            new_keys = set(source_data.keys()) - set(existing_dest_data.keys())
            updated_keys = set(source_data.keys()) & set(existing_dest_data.keys())

            if new_keys:
                logger.info(f"  🆕 New keys to add: {', '.join(new_keys)}")
            if updated_keys:
                logger.info(f"  ♻️ Keys to update: {', '.join(updated_keys)}")

        # Step 4: Write to destination vault
        vault_client.write_secret(dest_path, final_data)

        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ SECRET COPY COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"Source: {source_path}")
        logger.info(f"Destination: {dest_path}")
        logger.info(f"Keys copied: {len(source_data)}")
        logger.info(f"Total keys in destination: {len(final_data)}")
        logger.info("=" * 80)

        return (source_data, action)

    except VaultAPIError as e:
        logger.error(f"❌ Vault operation failed: {e}")
        return None
    except Exception as e:
        logger.exception(f"❌ Unexpected error: {e}")
        return None


def main():
    try:
        logger.info("=" * 80)
        logger.info("🔐 Vault Secret Copy Tool - Starting")
        logger.info("=" * 80)

        # Load configuration
        config = AppConfig.from_env()
        context = get_rundeck_context()

        if not config.vault.token:
            logger.error("Vault token is required")
            return 1

        if not config.vault.path:
            logger.error("Vault path is required")
            return 1

        # Log configuration
        logger.info(f"Vault address: {config.vault.addr}")
        logger.info(f"Vault path: {config.vault.path}")

        # Initialize Vault client
        vault_client = VaultClient(
            addr=config.vault.addr,
            token=config.vault.token,
            kv_version=1,  # Change to 2 if using KV v2
        )

        # Perform copy operation
        result = copy_vault_secret(
            vault_client=vault_client,
            source_path=context["source_vault_path"],
            dest_path=config.vault.path,
        )

        if not result:
            print("❌ Failed to copy secrets")
            return 1

        source_data, action = result
        keys = list(source_data.keys())
        context["action"] = action
        template_dir = Path(config.template_dir)
        yaml_generated = generate_vault_gke_yaml_to_git(
            keys, context, config, template_dir
        )

        if yaml_generated:
            logger.info("✅ YAML manifest generated successfully")
        else:
            logger.warning("⚠️ YAML generation skipped or failed (non-critical)")

    except VaultAPIError as e:
        logger.error(f"❌ Vault operation failed: {e}")
        print(f"Error: {e}")
        return 2
    except Exception as e:
        logger.exception(f"❌ Unexpected error: {e}")
        print(f"Error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
