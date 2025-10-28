# import argparse
import sys
import os
from typing import Dict, Optional, List
from pathlib import Path

from utils import (
    setup_logger,
    AppConfig,
    VaultClient,
    TemplateRenderError,
    TemplateRenderer,
    VaultAPIError
)

logger = setup_logger(__name__)


def get_rundeck_context() -> Dict[str, str]:
    context = {
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


def generate_vault_gke_yaml(
    deleted_keys: List[str],
    context: Dict[str, str],
    template_dir: Path,
    vault_path: str
) -> bool:
    try:
        # Template can be 'vault-gke.j2' or 'vault-delete.j2'
        # Using vault-gke.j2 for consistency with clone-vault.py
        template_file = template_dir / "vault-gke.j2"
        
        if not template_file.exists():
            logger.warning(f"Template '{template_file}' not found, skipping YAML generation")
            return False

        # Prepare template data
        template_data = {
            "ENV": context["env"],
            "vault_name": context["vault_name"],
            "namespace": context["namespace"],
            "action": context["action"],  # 'delete'
            "vault_keys": deleted_keys,
            "vault_path": vault_path
        }

        # Render template
        renderer = TemplateRenderer(template_dir=template_dir)
        
        # Save to file
        output_dir = Path(f"/tmp/{context['job_id']}")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"vault-delete-{context['exec_id']}.yaml"
        
        renderer.render_to_file("vault-gke.j2", template_data, output_file)
        
        logger.info(f"✅ YAML generated: {output_file}")
        return True
        
    except TemplateRenderError as e:
        logger.warning(f"YAML generation failed: {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error during YAML generation: {e}")
        return False


def delete_vault_secret(
    vault_client: VaultClient,
    vault_path: str,
    permanent: bool = False
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
            logger.info(f"Deletion type: {'PERMANENT (metadata)' if permanent else 'STANDARD'}")
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
            logger.error("❌ Vault path is required (set VAULT_PATH or use --vault-path)")
            return 1
        
        # Validate token
        if not config.vault.token:
            logger.error("❌ Vault token is required (set VAULT_TOKEN or RD_OPTION_VAULTTOKEN)")
            return 1
        
        # Log configuration
        logger.info(f"Vault address: {config.vault.addr}")
        logger.info(f"Vault path: {vault_path}")
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
            vault_path=vault_path,
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
        yaml_generated = generate_vault_gke_yaml(
            deleted_keys=deleted_keys,
            context=context,
            template_dir=template_dir,
            vault_path=vault_path
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
