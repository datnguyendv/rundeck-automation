#!/usr/bin/env python3
"""
Rundeck script: Generate approval job for vault key input
"""
import os
import sys
from pathlib import Path
from typing import Dict

from utils import (
    setup_logger,
    AppConfig,
    TemplateRenderer,
    RundeckClient,
    SlackNotifier,
    NotificationMessage,
    TemplateRenderError,
    RundeckAPIError,
    NotificationError,
    ConfigurationError
)

logger = setup_logger(__name__)


def get_rundeck_context() -> Dict[str, str]:
    """Extract Rundeck job context from environment"""
    context = {
        "job_id": os.getenv("RD_JOB_ID", "unknown_job"),
        "execution_uuid": os.getenv("RD_JOB_EXECUTIONUUID", "unknown_exec"),
        "exec_id": os.getenv("RD_JOB_EXECID", "0"),
        "user": os.getenv("RD_JOB_USERNAME", "system"),
    }
    logger.info(f"Rundeck context: job_id={context['job_id']}, user={context['user']}")
    return context


def generate_job_data(context: Dict[str, str]) -> Dict:
    """
    Generate job template data from environment variables
    
    Args:
        context: Rundeck execution context
    
    Returns:
        Job data dictionary for template rendering
    
    Raises:
        ConfigurationError: If required environment variables missing
    """
    try:
        # Read configuration from environment
        vault_name = os.getenv("RD_OPTION_VAULTNAME")
        namespace = os.getenv("RD_OPTION_NAMESPACE", "default")
        action = os.getenv("RD_OPTION_ACTION", "create")
        vault_keys_raw = os.getenv("RD_OPTION_VAULTKEY", "")
        
        if not vault_name:
            raise ConfigurationError("RD_OPTION_VAULTNAME is required")
        
        if not vault_keys_raw:
            raise ConfigurationError("RD_OPTION_VAULTKEY is required")
        
        # Parse vault keys
        vault_keys = [k.strip() for k in vault_keys_raw.split(",") if k.strip()]
        
        if not vault_keys:
            raise ConfigurationError("No valid vault keys provided")
        
        logger.info(f"Vault name: {vault_name}")
        logger.info(f"Namespace: {namespace}")
        logger.info(f"Action: {action}")
        logger.info(f"Vault keys: {', '.join(vault_keys)}")
        
        # Generate job name
        job_name = f"{action} vault value for {vault_name}"
        
        # Build job data structure
        result = {
            "options": [],
            "group": "approval",
            "name": job_name,
            "keys": vault_keys_raw,
            "job_id": context["job_id"],
            "execution_uuid": context["execution_uuid"],
        }
        
        # Add metadata options
        result["options"].extend([
            {"name": "VaultName", "description": "Vault secret name", "value": vault_name},
            {"name": "namespace", "description": "K8s namespace", "value": namespace},
            {"name": "Action", "description": "Action type", "value": action},
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
    """
    Main execution flow
    
    Returns:
        Exit code (0 = success, 1 = failure)
    """
    try:
        logger.info("=" * 80)
        logger.info("🚀 Vault Key Input Job Generator - Starting")
        logger.info("=" * 80)
        
        # Get execution context
        context = get_rundeck_context()
        
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
        
        config = AppConfig.from_env()
        rundeck = RundeckClient(
            url=config.rundeck.url,
            token=config.rundeck.token,
            project=config.rundeck.project
        )
        
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
