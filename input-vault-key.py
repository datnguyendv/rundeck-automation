import os
import sys
from pathlib import Path
from typing import Dict

from utils import (
    setup_logger,
    AppConfig,
    TemplateRenderer,
    RundeckClient,
    VaultClient,
    VaultAPIError,
    ValidationError,
    SlackNotifier,
    NotificationMessage,
    TemplateRenderError,
    RundeckAPIError,
    NotificationError,
    ConfigurationError
)

logger = setup_logger(__name__)

def get_rundeck_context() -> Dict[str, str]:
    context = {
        "job_id": os.getenv("RD_JOB_ID", "unknown_job"),
        "execution_uuid": os.getenv("RD_JOB_EXECUTIONUUID", "unknown_exec"),
        "exec_id": os.getenv("RD_JOB_EXECID", "0"),
        "user": os.getenv("RD_JOB_USERNAME", "system"),
        "vault_name": os.getenv("RD_OPTION_VAULTNAME"),
        "namespace": os.getenv("RD_OPTION_NAMESPACE", "default"),
        "action": os.getenv("RD_OPTION_ACTION", "create"),
        "vault_keys_raw": os.getenv("RD_OPTION_VAULTKEY", "")
    }
    logger.info(f"Rundeck context: job_id={context['job_id']}, user={context['user']}")
    return context


def generate_job_data(context: Dict[str, str]) -> Dict:
    try:
        # Read configuration from environment       
        if not context["vault_name"]:
            raise ConfigurationError("RD_OPTION_VAULTNAME is required")
        
        if not context["vault_keys_raw"]:
            raise ConfigurationError("RD_OPTION_VAULTKEY is required")
        
        # Parse vault keys
        vault_keys = [k.strip() for k in context["vault_keys_raw"].split(",") if k.strip()]
        
        if not vault_keys:
            raise ConfigurationError("No valid vault keys provided")
        
        logger.info(f"Vault name: {context['vault_name']}")
        logger.info(f"Namespace: {context['namespace']}")
        logger.info(f"Action: {context['action']}")
        logger.info(f"Vault keys: {', '.join(vault_keys)}")
        
        # Generate job name
        job_name = f"{context["action"]} vault value for {context['vault_name']}"
        
        # Build job data structure
        result = {
            "options": [],
            "group": "approval",
            "name": job_name.capitalize(),
            "keys": context['vault_keys_raw'],
            "job_id": context['job_id'],
            "execution_uuid": context['execution_uuid'],
        }
        
        # Add metadata options
        result["options"].extend([
            {"name": "VaultName", "description": "Vault secret name", "value": context['vault_name']},
            {"name": "namespace", "description": "K8s namespace", "value": context['namespace']},
            {"name": "Action", "description": "Action type", "value": context['action']},
        ])
        
        # Add secure VaultToken option
        result["options"].append({
            "name": "VaultToken",
            "description": "Vault authentication token",
            "required": True,
            "hidden": True,
            "secure": True,
            "storagePath": "keys/project/vault-management/Token",
            "valueExposed": True
        })
        
        # Add input fields for each vault key
        for key in vault_keys:
            result["options"].append({
                "name": key,
                "description": f"Value for secret key {key}",
                "required": True
            })
        
        logger.debug(f"Generated job data: {result}")
        return result
    
    except Exception as e:
        logger.error(f"Failed to generate job data: {e}")
        raise


def main() -> int:
    try:
        logger.info("=" * 80)
        logger.info("🚀 Vault Key Input Job Generator - Starting")
        logger.info("=" * 80)
        
        # Get execution context
        context = get_rundeck_context()
        config = AppConfig.from_env()
        rundeck = RundeckClient(
            url=config.rundeck.url,
            token=config.rundeck.token,
            project=config.rundeck.project
        )
        vault_client = VaultClient(
            addr=config.vault.addr,
            token=config.vault.token,
        )
        if context["action"] == "create":
            existing_secret = vault_client.read_secret(config.vault.path)
            
            # Secret exists → raise error WITHOUT logging here
            error_msg = (
                f"❌ VALIDATION FAILED: Secret already exists at path '{config.vault.path}'\n"
                f"Cannot create a secret that already exists.\n"
                f"Please contact admin (SRE team) or use action 'update'/'delete'."
            )
            logger.error(error_msg)
            # raise ValidationError(error_msg)  # Raise without logging
            return 1
        # Setup paths
        base_dir = Path(__file__).resolve().parent
        output_dir = Path(f"/tmp/{context['job_id']}/{context['execution_uuid']}")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"approval_job_{context['exec_id']}.yaml"
        
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Output file: {output_file}")
        
        # Step 1: Generate job data
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: Generating job data")
        logger.info("=" * 80)
        
        job_data = generate_job_data(context)
        job_name = job_data["name"]
        
        # Step 2: Render template
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Rendering job template")
        logger.info("=" * 80)
        
        template_dir = base_dir / "template"
        renderer = TemplateRenderer(template_dir=template_dir)
        renderer.render_to_file("vault-value.j2", job_data, output_file)
        
        # Step 3: Import to Rundeck
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Importing job to Rundeck")
        logger.info("=" * 80)
        
        response_data = rundeck.import_job(output_file)
        job_link = rundeck.get_job_permalink(response_data)
        
        # Step 4: Send notification
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Sending Slack notification")
        logger.info("=" * 80)
        
        if config.slack.enabled:
            notifier = SlackNotifier(webhook_url=config.slack.webhook_url)
            message = NotificationMessage(
                title=job_name,
                link=job_link,
                user=context["user"]
            )
            notifier.send(message)
        else:
            logger.warning("Slack notifications disabled (no webhook URL)")
        
        # Success
        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL STEPS COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        
        return 0
    
    except (TemplateRenderError, RundeckAPIError, ConfigurationError) as e:
        logger.error(f"❌ Operation failed: {e}")
        return 1
    
    except NotificationError as e:
        logger.warning(f"⚠️ Notification failed (non-critical): {e}")
        return 0  # Don't fail the whole job for notification issues
    
    except Exception as e:
        logger.exception(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
