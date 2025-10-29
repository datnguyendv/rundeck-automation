import os
from dataclasses import dataclass
from typing import Optional, Dict, Any

from .exceptions import VaultAPIError
from .vault_client import VaultClient
from .logger import setup_logger

logger = setup_logger(__name__)

def load_secrets_from_vault(vault_client: VaultClient, path: str) -> Dict[str, Any]:
    try:
        logger.info(f"Reading secret data from Vault path {path} ...")
        secretdata = vault_client.read_secret(path)
        
        if not secretdata:
            logger.warning("Secret exists but contains no keys.")
            return {}
        
        logger.info(f"Successfully loaded {len(secretdata)} secrets from Vault")
        for key in secretdata.keys():
            logger.info(f"Loaded secret key: {key}")
        
        return secretdata
    
    except VaultAPIError as e:
        logger.error(f"Vault operation failed: {e}")
        raise
    
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise

@dataclass
class RundeckConfig:
    """Rundeck configuration"""
    url: str
    token: str
    project: str

    @classmethod
    def from_env(cls, rd_token: str, rd_url: str=None) -> 'RundeckConfig':
        if not rd_token:
            raise ValueError("RD_TOKEN environment variable is required")

        return cls(
            url= rd_url,
            token=rd_token,
            project=os.getenv("RD_PROJECT", "vault-management")
        )

@dataclass
class VaultConfig:
    """Vault configuration"""
    addr: str
    token: Optional[str]
    path: str

    @classmethod
    def from_env(cls, vault_addr: str, vault_token: Optional[str] = None) -> 'VaultConfig':
        return cls(
            addr=vault_addr,
            token=vault_token,
            path=os.getenv("VAULT_PATH", f"gke/{os.getenv('RD_OPTION_VAULTNAME')}")
        )

@dataclass
class SlackConfig:
    webhook_url: str
    enabled: bool = True
    
    @classmethod
    def from_env(cls, webhook_url: Optional[str] = None) -> 'SlackConfig':
        return cls(
            webhook_url=webhook_url,
            enabled=bool(webhook_url)
        )

@dataclass
class AppConfig:
    """Application configuration"""
    rundeck: RundeckConfig
    vault: VaultConfig
    slack: SlackConfig
    template_dir: str
    output_dir: str
    
    @classmethod
    def from_env(cls, vault_token: Optional[str] = None, vault_path: Optional[str] = 'gke/ct-rundeck-env') -> 'AppConfig':
        vault_secrets = {}
        env = os.environ.get("RD_OPTION_ENV", "dev")
        # Load secrets from Vault if vault_path is provided
        try:
            # Determine vault address
            addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
            
            if not vault_token:
                vault_token = os.getenv("RD_OPTION_VAULTTOKEN")
                if not vault_token:
                    logger.error("Vault token is required but not provided.")
                    raise ValueError("Vault token must be provided.")                
                else:
                    # Create Vault client and load secrets
                    vault_client = VaultClient(addr, vault_token)
                    vault_secrets = load_secrets_from_vault(vault_client, vault_path)
            else:
                # Create Vault client and load secrets
                vault_client = VaultClient(addr, vault_token)
                vault_secrets = load_secrets_from_vault(vault_client, vault_path)
            # print("test", vault_secrets[f"VAULT_ADDR_{env.upper()}"])
                
        except Exception as e:
            logger.error(f"Failed to load secrets from Vault: {e}")
            logger.warning("Continuing with environment variables only")
    
        # Initialize all configs with vault_secrets
        return cls(
            rundeck=RundeckConfig.from_env(vault_secrets["RD_TOKEN"], vault_secrets["RD_URL"]),
            vault=VaultConfig.from_env(vault_secrets[f"VAULT_ADDR_{env.upper()}"], vault_secrets[f"VAULT_TOKEN_{env.upper()}"]),
            slack=SlackConfig.from_env(vault_secrets["SLACK_WEBHOOK_URL"]),
            template_dir= f'{os.getenv("EXEC_LOCATION", ".")}/template',
            output_dir= os.getenv("OUTPUT_DIR", "/tmp"),
        )
