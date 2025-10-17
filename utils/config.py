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
            path=os.getenv("VAULT_PATH", f"gke/{os.getenv("RD_OPTION_VAULTTOKEN")}")
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
