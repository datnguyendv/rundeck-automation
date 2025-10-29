import os
from utils import (setup_logger, AppConfig, VaultClient, VaultAPIError)

logger = setup_logger(__name__)

def export_secret_to_env(vault_client: VaultClient, path: str):
    try:
        logger.info(f"Reading secret data from Vault path {path} ...")
        secretdata = vault_client.read_secret(path)
        if not secretdata:
            logger.warning("Secret exists but contains no keys.")
            return 1

        for key, value in secretdata.items():
            os.environ[str(key)] = str(value)
            logger.info(f"Exported {key} to environment.")
        return 0

    except VaultAPIError as e:
        errormsg = str(e).lower()
        logger.error(f"Vault operation failed: {e}")
        print("Error: Unable to read from Vault")
        return 2
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print("Error: Unexpected error occurred")
        return 2

def main():
    config = AppConfig.from_env()
    if not config.vault.token or not config.vault.path:
        print("Vault token/path not provided")
        return 2
    vault_client = VaultClient(addr=config.vault.addr, token=config.vault.token)
    return export_secret_to_env(vault_client, "gke/ct-rundeck-env")

if __name__ == "__main__":
    import sys
    sys.exit(main())
