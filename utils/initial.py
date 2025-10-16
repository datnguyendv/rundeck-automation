import os
import sys
import logging
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class VaultClientV1:
    def __init__(self, addr: str, token: str, timeout: int = 15):
        self.addr = addr.rstrip('/')
        self.token = token
        self.timeout = timeout
    
    def _headers(self) -> Dict[str, str]:
        return {
            "X-Vault-Token": self.token,
            "Content-Type": "application/json"
        }
    
    def read_secret(self, path: str) -> Optional[Dict[str, Any]]:
        url = f"{self.addr}/v1/{path.lstrip('/')}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            # KV v1: secrets are directly in data['data']
            secret_data = data.get('data', {})
            logger.info(f"Read {len(secret_data)} secrets from Vault path {path}")
            return secret_data
        except Exception as e:
            logger.error(f"Failed to get secret from Vault at path {path}: {e}")
            return None

def export_secrets_to_env(secrets: Dict[str, Any], prefix: str = "") -> None:
    if not secrets:
        logger.warning("No secrets to export")
        return
    
    for key, value in secrets.items():
        # Env var name upper case + optional prefix
        env_key = prefix + key.upper()
        env_val = str(value)
        os.environ[env_key] = env_val
        logger.info(f"Exported env var {env_key}")

def initialize_vault_env(
    vault_addr: Optional[str] = None,
    vault_token: Optional[str] = None,
    vault_path: Optional[str] = None,
    env_prefix: str = ""
) -> bool:
    vault_addr = vault_addr or os.getenv("VAULT_ADDR", "https://vault.example.com")
    vault_token = vault_token or os.getenv("VAULT_TOKEN") or os.getenv("RD_OPTION_VAULTTOKEN")
    vault_path = vault_path or os.getenv("VAULT_PATH")
    
    if not vault_token:
        logger.error("Missing Vault token. Set VAULT_TOKEN or RD_OPTION_VAULTTOKEN env var.")
        return False
    
    if not vault_path:
        logger.error("Missing Vault path. Set VAULT_PATH env var.")
        return False
    
    client = VaultClientV1(vault_addr, vault_token)
    secrets = client.read_secret(vault_path)
    
    if secrets is None:
        logger.error("Failed to retrieve secrets from Vault.")
        return False
    
    export_secrets_to_env(secrets, prefix=env_prefix)
    logger.info("Vault secrets loaded and env vars set.")
    return True
