"""
HashiCorp Vault API client
"""
import logging
import json
from typing import Dict, Any, Optional
import requests

from .exceptions import VaultAPIError
from .logger import setup_logger

logger = setup_logger(__name__)


class VaultClient:
    """HashiCorp Vault KV v2 client"""
    
    def __init__(self, addr: str, token: str, timeout: int = 30):
        """
        Initialize Vault client
        
        Args:
            addr: Vault server address
            token: Vault authentication token
            timeout: Request timeout in seconds
        """
        self.addr = addr.rstrip('/')
        self.token = token
        self.timeout = timeout
        
        logger.info(f"Initialized VaultClient for {self.addr}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        return {
            "X-Vault-Token": self.token,
            "Content-Type": "application/json"
        }
    
    def write_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """
        Write secret to Vault KV v2
        
        Args:
            path: Vault path (e.g., 'secret/data/dev')
            data: Secret data dictionary
        
        Returns:
            True if successful
        
        Raises:
            VaultAPIError: If write fails
        """
        if not self.token:
            raise VaultAPIError("Vault token is required")
        
        # KV v2 format
        # payload = {"data": data}
        url = f"{self.addr}/v1/{path}"
        
        logger.info(f"📝 Writing secrets to Vault path: {path}")
        logger.debug(f"Secret keys: {list(data.keys())}")
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=data,
                timeout=self.timeout
            )
            
            if response.status_code in [200, 204]:
                logger.info("✅ Secrets written to Vault successfully")
                return True
            else:
                error_msg = f"Vault API error: {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {json.dumps(error_detail)}"
                except:
                    error_msg += f" - {response.text}"
                logger.error(error_msg)
                raise VaultAPIError(error_msg)
        
        except requests.exceptions.Timeout:
            error_msg = f"Vault request timeout after {self.timeout}s"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Vault request failed: {str(e)}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
    
    def read_secret(self, path: str) -> Dict[str, Any]:
        """
        Read secret from Vault KV v2
        
        Args:
            path: Vault path
        
        Returns:
            Secret data dictionary
        
        Raises:
            VaultAPIError: If read fails
        """
        url = f"{self.addr}/v1/{path}"
        
        logger.info(f"📖 Reading secrets from Vault path: {path}")
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            result = response.json()
            data = result.get("data", {}).get("data", {})
            
            logger.info(f"✅ Read {len(data)} secrets from Vault")
            return data
        
        except requests.exceptions.HTTPError as e:
            error_msg = f"Vault API error: {e.response.status_code}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
        
        except Exception as e:
            error_msg = f"Failed to read from Vault: {str(e)}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
