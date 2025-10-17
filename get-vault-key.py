import argparse
import sys
from typing import List, Optional

from utils import (
    setup_logger,
    AppConfig,
    VaultClient,
    VaultAPIError
)

logger = setup_logger(__name__)

def get_secret_keys(vault_client: VaultClient, path: str) -> Optional[List[str]]:
    try:
        logger.info(f"Reading secret keys from Vault path: {path}")
        
        # Read secret data
        secret_data = vault_client.read_secret(path)
        
        if not secret_data:
            logger.warning("Secret exists but contains no keys")
            return []
        
        # Extract keys only (not values)
        keys = list(secret_data.keys())
        
        logger.info(f"✅ Found {len(keys)} keys in Vault")
        return keys
    
    except VaultAPIError as e:
        error_msg = str(e).lower()
        
        # Check if it's a 404 (not found)
        if "404" in error_msg or "not found" in error_msg:
            logger.warning(f"Secret not found at path: {path}")
            return None
        else:
            # Re-raise other errors
            raise


def format_output(keys: Optional[List[str]], output_format: str) -> str:
    if keys is None:
        return "Secret does not exist or not found"
    
    if not keys:
        return "Secret exists but contains no keys"
    
    if output_format == "comma":
        return ",".join(keys)
    elif output_format == "space":
        return " ".join(keys)
    elif output_format == "json":
        import json
        return json.dumps(keys, indent=2)
    else:  # list format (default)
        return "\n".join(keys)


def main() -> int:
    try:
        logger.info("=" * 80)
        logger.info("🔑 Vault Key Getter - Starting")
        logger.info("=" * 80)
       
        # Load application configuration (includes Vault, Rundeck, Slack)
        config = AppConfig.from_env()
              
        # Validate required config
        if not config.vault.token:
            logger.error("Vault token is required")
            print("Error: Vault token not provided")
            return 2
        
        if not config.vault.path:
            logger.error("Vault path is required")
            print("Error: Vault path not provided")
            return 2
        
        # Log configuration
        logger.info(f"Vault address: {config.vault.addr}")
        logger.info(f"Vault path: {config.vault.path}")
        # logger.info(f"Output format: {args.output_format}")
        
        # Initialize Vault client using AppConfig
        vault_client = VaultClient(
            addr=config.vault.addr,
            token=config.vault.token,
            # kv_version=config.vault.kv_version
        )
        
        # Get secret keys
        keys = get_secret_keys(vault_client, config.vault.path)
        
        # Format and print output
        output = format_output(keys, "comma")
        
        # Determine exit code
        if keys is None:
            logger.info("Exit code: 1 (not found)")
            return 1
        elif not keys:
            logger.info("Exit code: 0 (empty secret)")
            return 0
        else:
            # Print to stdout (for capture by other scripts)
            print(f"Vault name: {config.vault.path.split('/',1)[1]}")
            print(f"Key       : {output}")
            return 0
    
    except VaultAPIError as e:
        logger.error(f"❌ Vault operation failed: {e}")
        print("Error: Unable to read from Vault")
        return 2
    
    except Exception as e:
        logger.exception(f"❌ Unexpected error: {e}")
        print("Error: Unexpected error occurred")
        return 2


if __name__ == "__main__":
    sys.exit(main())

