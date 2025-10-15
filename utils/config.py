"""
Centralized configuration management
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class RundeckConfig:
    """Rundeck configuration"""
    url: str
    token: str
    project: str
    
    @classmethod
    def from_env(cls) -> 'RundeckConfig':
        """Load from environment variables"""
        token = os.getenv("RD_TOKEN", "Vczci5ltVL6coadjTQyemtAmML9lNJLU")
        if not token:
            raise ValueError("RD_TOKEN environment variable is required")
        
        return cls(
            url=os.getenv("RD_URL", "http://localhost:4440"),
            token=token,
            project=os.getenv("RD_PROJECT", "vault-management")
        )


@dataclass
class VaultConfig:
    """Vault configuration"""
    addr: str
    token: Optional[str]
    path: str
    
    @classmethod
    def from_env(cls, vault_token: Optional[str] = None) -> 'VaultConfig':
        """Load from environment variables"""
        return cls(
            addr=os.getenv("VAULT_ADDR", "https://vault.example.com"),
            token=vault_token or os.getenv("RD_OPTION_VAULTTOKEN"),
            path=os.getenv("VAULT_PATH", "secret/data/dev")
        )


@dataclass
class SlackConfig:
    """Slack configuration"""
    webhook_url: str
    enabled: bool = True
    
    @classmethod
    def from_env(cls) -> 'SlackConfig':
        """Load from environment variables"""
        webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
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
    def from_env(cls, vault_token: Optional[str] = None) -> 'AppConfig':
        """Load all configurations from environment"""
        return cls(
            rundeck=RundeckConfig.from_env(),
            vault=VaultConfig.from_env(vault_token),
            slack=SlackConfig.from_env(),
            template_dir=os.getenv("TEMPLATE_DIR", "./template"),
            output_dir=os.getenv("OUTPUT_DIR", "/tmp")
        )


# @dataclass
# class VaultConfig:
#     """Vault configuration"""
#     addr: str
#     token: Optional[str]
#     path: str
#     kv_version: int = 1  # Default to KV v1
#
#     @classmethod
#     def from_env(cls, vault_token: Optional[str] = None) -> 'VaultConfig':
#         """Load from environment variables"""
#         # Read KV version from env (default to 1)
#         kv_version_str = os.getenv("VAULT_KV_VERSION", "1")
#         try:
#             kv_version = int(kv_version_str)
#             if kv_version not in [1, 2]:
#                 kv_version = 1
#         except ValueError:
#             kv_version = 1
#
#         return cls(
#             addr=os.getenv("VAULT_ADDR", "https://vault.example.com"),
#             token=vault_token or os.getenv("RD_OPTION_VAULTTOKEN"),
#             path=os.getenv("VAULT_PATH", "secret/data/dev"),
#             kv_version=kv_version
#         )

