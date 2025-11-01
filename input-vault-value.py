import argparse
import os
import sys
from pathlib import Path
from typing import List, Dict

from utils import (
    setup_logger,
    AppConfig,
    TemplateRenderer,
    VaultClient,
    GitClient,
    GitOperationError,
    VaultAPIError,
    TemplateRenderError,
    ValidationError,
)

logger = setup_logger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse and validate command line arguments"""
    parser = argparse.ArgumentParser(
        description="Import secrets into HashiCorp Vault (KV v1 or v2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import from Rundeck options (uses env vars)
  python vault_value_input.py -i GITHUB_TOKEN,NPM_TOKEN

  # Override Vault settings
  python vault_value_input.py -i API_KEY \\

  # Skip YAML generation
  python vault_value_input.py -i DB_PASSWORD --skip-yaml
        """,
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Comma-separated list of secret keys (e.g., GITHUB_TOKEN,NPM_TOKEN)",
    )
    parser.add_argument(
        "--skip-yaml", action="store_true", help="Skip YAML generation step"
    )

    return parser.parse_args()


def parse_input_keys(input_string: str) -> List[str]:
    keys = [k.strip() for k in input_string.split(",") if k.strip()]

    if not keys:
        raise ValidationError("No valid secret keys provided")

    logger.info(f"Parsed {len(keys)} secret keys: {', '.join(keys)}")
    return keys


def get_rundeck_context() -> Dict[str, str]:
    context = {
        "env": os.environ.get("RD_OPTION_ENV", "dev"),
        "vault_name": os.environ.get("RD_OPTION_VAULTNAME", "default-service"),
        "namespace": os.environ.get("RD_OPTION_NAMESPACE", "default"),
        "action": os.environ.get("RD_OPTION_ACTION", "create"),
        "job_id": os.environ.get("RD_JOB_ID", "default"),
        "exec_id": os.environ.get("RD_JOB_EXECID", "0"),
    }

    logger.info(f"Rundeck context: env={context['env']}, vault={context['vault_name']}")
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
        repo_local_path = Path(config.output_dir) / f"config-repo-{context['exec_id']}"

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
        commit_message = f"Update input.yaml for {context['env']} - {context['vault_name']} (Job: {context['job_id']}, User: {config.git.username})"

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


def generate_vault_gke_yaml(
    keys: List[str], context: Dict[str, str], template_dir: Path
) -> bool:
    try:
        # Prepare template data
        template_data = {
            "ENV": context["env"],
            "vault_name": context["vault_name"],
            "namespace": context["namespace"],
            "action": context["action"],
            "vault_keys": keys,
        }

        # Render template
        renderer = TemplateRenderer(template_dir=template_dir)

        # Save to file
        output_dir = Path(f"/tmp/{context['job_id']}")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"vault-gke-{context['exec_id']}.yaml"

        renderer.render_to_file("vault-gke.j2", template_data, output_file)
        logger.info(f"✅ YAML generated: {output_file}")

        return True

    except TemplateRenderError as e:
        logger.warning(f"YAML generation failed: {e}")
        return False


def gather_secret_data(keys: List[str]) -> Dict[str, str]:
    data_dict = {}
    missing_keys = []

    for key in keys:
        env_var = f"RD_OPTION_{key}"
        value = os.environ.get(env_var)

        if value is None:
            logger.warning(f"Missing environment variable: {env_var}")
            missing_keys.append(key)
            value = ""
        else:
            # Don't log actual secret values
            logger.debug(f"Found value for {key}")

        data_dict[key] = value

    if missing_keys:
        logger.warning(
            f"Total missing keys: {len(missing_keys)} - {', '.join(missing_keys)}"
        )

    logger.info(f"Gathered {len(data_dict)} secret values")
    return data_dict


def main() -> int:
    try:
        logger.info("=" * 80)
        logger.info("🚀 Vault Secret Importer - Starting")
        logger.info("=" * 80)

        # Parse arguments
        args = parse_arguments()
        keys = parse_input_keys(args.input)

        # Load application configuration using AppConfig
        config = AppConfig.from_env()

        # Override with command-line arguments if provided
        # Validate required config
        if not config.vault.token:
            logger.error("Vault token is required")
            return 1

        if not config.vault.path:
            logger.error("Vault path is required")
            return 1

        # Log configuration
        logger.info(f"Vault address: {config.vault.addr}")
        logger.info(f"Vault path: {config.vault.path}")

        # Get Rundeck context
        rundeck_context = get_rundeck_context()
        # Step 1: Gather secrets
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Gathering secret values")
        logger.info("=" * 80)

        secret_data = gather_secret_data(keys)

        # Step 2: Write to Vault
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Writing secrets to Vault")
        logger.info("=" * 80)

        # Initialize Vault client using AppConfig
        vault_client = VaultClient(
            addr=config.vault.addr,
            token=config.vault.token,
            # kv_version=config.vault.kv_version
        )

        if rundeck_context["action"] == "add":
            vault_client.put_secret(config.vault.path, secret_data)
        else:
            vault_client.write_secret(config.vault.path, secret_data)
        # vault_client.write_secret(config.vault.path, secret_data)

        # Step 3: Generate YAML (optional)
        if not args.skip_yaml:
            logger.info("\\n" + "=" * 80)
            logger.info("STEP 1: Generating vault-gke YAML")
            logger.info("=" * 80)
            template_dir = Path(config.template_dir)
            # Use Git workflow if available and not skipped
            if config.git:
                yaml_success = generate_vault_gke_yaml_to_git(
                    keys, rundeck_context, config, template_dir
                )
            else:
                # Fallback to legacy /tmp behavior
                logger.info("Using legacy /tmp YAML generation")
                yaml_success = generate_vault_gke_yaml(
                    keys, rundeck_context, template_dir
                )

            if not yaml_success:
                logger.warning("⚠️ YAML generation failed (non-critical)")
        else:
            logger.info("Skipping YAML generation (--skip-yaml)")

        # Success
        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL STEPS COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)

        return 0

    except (ValidationError, VaultAPIError, TemplateRenderError) as e:
        logger.error(f"❌ Operation failed: {e}")
        return 1

    except Exception as e:
        logger.exception(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
