import logging
import json
from typing import Dict, Any, Optional, Literal, List
import requests

from .exceptions import VaultAPIError
from .logger import setup_logger

logger = setup_logger(__name__)


class VaultClient:
    def __init__(
        self, 
        addr: str, 
        token: str, 
        kv_version: Literal[1, 2] = 1,
        timeout: int = 30
    ):
        if kv_version not in [1, 2]:
            raise ValueError("kv_version must be 1 or 2")
        self.addr = addr.rstrip('/')
        self.token = token
        self.kv_version = kv_version
        self.timeout = timeout
        
        logger.info(f"Initialized VaultClient for {self.addr} (KV v{kv_version})")
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Vault-Token": self.token,
            "Content-Type": "application/json"
        }
    
    def write_secret(self, path: str, data: Dict[str, Any]) -> bool:
        if not self.token:
            raise VaultAPIError("Vault token is required")
        
        # Prepare payload based on KV version
        if self.kv_version == 1:
            # KV v1: direct data
            payload = data
            url = f"{self.addr}/v1/{path}"
        else:
            # KV v2: wrapped in "data" field
            payload = {"data": data}
            url = f"{self.addr}/v1/{path}"
        
        logger.info(f"Writing secrets to Vault (KV v{self.kv_version})")
        logger.info(f"Path: {path}")
        logger.debug(f"Secret keys: {list(data.keys())}")
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )
            
            # KV v1 returns 204 (No Content)
            # KV v2 returns 200 with response body
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
    
    def read_secret(self, path: str, version: Optional[int] = None) -> Dict[str, Any]:
        """
        Read secret from Vault
        
        Args:
            path: Vault path
                  - For KV v1: 'secret/myapp'
                  - For KV v2: 'secret/data/myapp'
            version: (KV v2 only) Specific version to read
        
        Returns:
            Secret data dictionary
        
        Raises:
            VaultAPIError: If read fails
        """
        url = f"{self.addr}/v1/{path}"
        
        # Add version parameter for KV v2
        params = {}
        if self.kv_version == 2 and version is not None:
            params['version'] = version
        
        logger.info(f"Reading secrets from Vault (KV v{self.kv_version})")
        logger.info(f"Path: {path}")
        if version:
            logger.info(f"Version: {version}")
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract data based on KV version
            if self.kv_version == 1:
                # KV v1: data is at root level
                data = result.get("data", {})
            else:
                # KV v2: data is nested under data.data
                data = result.get("data", {}).get("data", {})
            
            logger.info(f"✅ Read {len(data)} secrets from Vault")
            return data
        
        except requests.exceptions.HTTPError as e:
            error_msg = f"Vault API error: {e.response.status_code}"
            if e.response.status_code == 404:
                error_msg = f"Secret not found at path: {path}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
        
        except Exception as e:
            error_msg = f"Failed to read from Vault: {str(e)}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
    
    def delete_secret(self, path: str) -> bool:
        """
        Delete secret from Vault
        
        For KV v1: Permanently deletes the secret
        For KV v2: Soft delete (marks latest version as deleted, can be undeleted)
        
        Args:
            path: Vault path
                  - For KV v1: 'secret/myapp'
                  - For KV v2: 'secret/data/myapp'
        
        Returns:
            True if successful
        
        Raises:
            VaultAPIError: If deletion fails
        """
        url = f"{self.addr}/v1/{path}"
        
        logger.info(f"Deleting secret from Vault (KV v{self.kv_version})")
        logger.info(f"Path: {path}")
        
        try:
            response = requests.delete(
                url,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code in [200, 204]:
                if self.kv_version == 1:
                    logger.info("✅ Secret permanently deleted (KV v1)")
                else:
                    logger.info("✅ Secret soft-deleted (KV v2 - can be undeleted)")
                return True
            elif response.status_code == 404:
                logger.warning("⚠️ Secret not found (may already be deleted)")
                return False
            else:
                response.raise_for_status()
                return False
        
        except requests.exceptions.HTTPError as e:
            error_msg = f"Failed to delete secret: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {json.dumps(error_detail)}"
            except:
                error_msg += f" - {e.response.text}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
        
        except Exception as e:
            error_msg = f"Failed to delete secret: {str(e)}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
    
    def delete_versions(self, path: str, versions: List[int]) -> bool:
        """
        Delete specific versions of a secret (KV v2 only)
        
        Args:
            path: Vault metadata path (e.g., 'secret/metadata/myapp')
            versions: List of version numbers to delete
        
        Returns:
            True if successful
        
        Raises:
            VaultAPIError: If deletion fails or using KV v1
        """
        if self.kv_version == 1:
            raise VaultAPIError("delete_versions is only available for KV v2")
        
        # Convert path from data to delete endpoint
        # secret/data/myapp -> secret/delete/myapp
        delete_path = path.replace('/data/', '/delete/')
        url = f"{self.addr}/v1/{delete_path}"
        
        payload = {"versions": versions}
        
        logger.info(f"Deleting specific versions from Vault (KV v2)")
        logger.info(f"Path: {delete_path}")
        logger.info(f"Versions: {versions}")
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"✅ Deleted versions {versions} successfully")
                return True
            else:
                response.raise_for_status()
                return False
        
        except requests.exceptions.HTTPError as e:
            error_msg = f"Failed to delete versions: {e.response.status_code}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
        
        except Exception as e:
            error_msg = f"Failed to delete versions: {str(e)}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
    
    def undelete_versions(self, path: str, versions: List[int]) -> bool:
        """
        Undelete specific versions of a secret (KV v2 only)
        
        Args:
            path: Vault path (e.g., 'secret/data/myapp')
            versions: List of version numbers to undelete
        
        Returns:
            True if successful
        
        Raises:
            VaultAPIError: If undelete fails or using KV v1
        """
        if self.kv_version == 1:
            raise VaultAPIError("undelete_versions is only available for KV v2")
        
        # Convert path from data to undelete endpoint
        # secret/data/myapp -> secret/undelete/myapp
        undelete_path = path.replace('/data/', '/undelete/')
        url = f"{self.addr}/v1/{undelete_path}"
        
        payload = {"versions": versions}
        
        logger.info(f"Undeleting versions from Vault (KV v2)")
        logger.info(f"Path: {undelete_path}")
        logger.info(f"Versions: {versions}")
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"✅ Undeleted versions {versions} successfully")
                return True
            else:
                response.raise_for_status()
                return False
        
        except requests.exceptions.HTTPError as e:
            error_msg = f"Failed to undelete versions: {e.response.status_code}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
        
        except Exception as e:
            error_msg = f"Failed to undelete versions: {str(e)}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
    
    def destroy_versions(self, path: str, versions: List[int]) -> bool:
        """
        Permanently destroy specific versions of a secret (KV v2 only)
        This operation is irreversible!
        
        Args:
            path: Vault path (e.g., 'secret/data/myapp')
            versions: List of version numbers to destroy
        
        Returns:
            True if successful
        
        Raises:
            VaultAPIError: If destroy fails or using KV v1
        """
        if self.kv_version == 1:
            raise VaultAPIError("destroy_versions is only available for KV v2")
        
        # Convert path from data to destroy endpoint
        # secret/data/myapp -> secret/destroy/myapp
        destroy_path = path.replace('/data/', '/destroy/')
        url = f"{self.addr}/v1/{destroy_path}"
        
        payload = {"versions": versions}
        
        logger.warning(f"⚠️ PERMANENTLY destroying versions from Vault (KV v2)")
        logger.warning(f"Path: {destroy_path}")
        logger.warning(f"Versions: {versions}")
        logger.warning("This operation is IRREVERSIBLE!")
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"✅ Permanently destroyed versions {versions}")
                return True
            else:
                response.raise_for_status()
                return False
        
        except requests.exceptions.HTTPError as e:
            error_msg = f"Failed to destroy versions: {e.response.status_code}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
        
        except Exception as e:
            error_msg = f"Failed to destroy versions: {str(e)}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
    
    def delete_metadata(self, path: str) -> bool:
        if self.kv_version == 1:
            raise VaultAPIError("delete_metadata is only available for KV v2")
        
        # Convert path from data to metadata endpoint
        # secret/data/myapp -> secret/metadata/myapp
        metadata_path = path.replace('/data/', '/metadata/')
        url = f"{self.addr}/v1/{metadata_path}"
        
        logger.warning(f"⚠️ Deleting ALL metadata and versions from Vault (KV v2)")
        logger.warning(f"Path: {metadata_path}")
        logger.warning("This will permanently delete ALL versions!")
        
        try:
            response = requests.delete(
                url,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code in [200, 204]:
                logger.info("✅ Metadata and all versions deleted permanently")
                return True
            elif response.status_code == 404:
                logger.warning("⚠️ Metadata not found (may already be deleted)")
                return False
            else:
                response.raise_for_status()
                return False
        
        except requests.exceptions.HTTPError as e:
            error_msg = f"Failed to delete metadata: {e.response.status_code}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
        
        except Exception as e:
            error_msg = f"Failed to delete metadata: {str(e)}"
            logger.error(error_msg)
            raise VaultAPIError(error_msg)
