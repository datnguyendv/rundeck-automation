import os
from .exceptions import VaultAPIError
from .vault_client import VaultClient
from .logger import setup_logger

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

