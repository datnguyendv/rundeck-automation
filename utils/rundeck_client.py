"""
Rundeck API client with retry logic and better error handling
"""
import logging
import json
import time
from pathlib import Path
from typing import Dict, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import RundeckAPIError
from .logger import setup_logger

logger = setup_logger(__name__)


class RundeckClient:
    """Rundeck API client with automatic retry"""
    
    def __init__(
        self,
        url: str,
        token: str,
        project: str,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize Rundeck client
        
        Args:
            url: Rundeck base URL
            token: API authentication token
            project: Project name
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.url = url.rstrip('/')
        self.token = token
        self.project = project
        self.timeout = timeout
        
        # Setup session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,  # 1s, 2s, 4s delays
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        logger.info(f"Initialized RundeckClient for {self.url}")
    
    def _get_headers(self, content_type: str = "application/yaml") -> Dict[str, str]:
        """Get request headers"""
        return {
            "X-Rundeck-Auth-Token": self.token,
            "Content-Type": content_type,
            "Accept": "application/json"
        }
    
    def import_job(self, yaml_file: Path, duplicate_option: str = "update") -> Dict:
        """
        Import job from YAML file
        
        Args:
            yaml_file: Path to YAML job definition
            duplicate_option: How to handle duplicates (update/skip/create)
        
        Returns:
            Response data dictionary
        
        Raises:
            RundeckAPIError: If import fails
        """
        if not yaml_file.exists():
            raise RundeckAPIError(f"YAML file not found: {yaml_file}")
        
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
            
            url = f"{self.url}/api/54/project/{self.project}/jobs/import"
            params = {"dupeOption": duplicate_option}
            
            logger.info(f"📤 Importing job from {yaml_file.name}")
            logger.debug(f"API URL: {url}")
            logger.debug(f"Duplicate option: {duplicate_option}")
            
            response = self.session.post(
                url,
                headers=self._get_headers("application/yaml"),
                params=params,
                data=yaml_content.encode('utf-8'),
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            response_data = response.json()
            logger.info("✅ Job imported successfully")
            logger.debug(f"Response: {json.dumps(response_data, indent=2)}")
            
            return response_data
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"Rundeck API error: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {json.dumps(error_detail)}"
            except:
                error_msg += f" - {e.response.text}"
            logger.error(error_msg)
            raise RundeckAPIError(error_msg)
        
        except requests.exceptions.Timeout:
            error_msg = f"Request timeout after {self.timeout}s"
            logger.error(error_msg)
            raise RundeckAPIError(error_msg)
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)
            raise RundeckAPIError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            raise RundeckAPIError(error_msg)
    
    def get_job_permalink(self, response_data: Dict) -> str:
        """
        Extract job permalink from import response
        
        Args:
            response_data: Response from import_job
        
        Returns:
            Job permalink URL or 'N/A'
        """
        try:
            if "succeeded" in response_data and response_data["succeeded"]:
                job_info = response_data["succeeded"][0]
                permalink = job_info.get("permalink") or job_info.get("href", "N/A")
                logger.info(f"🔗 Job permalink: {permalink}")
                return permalink
            elif "failed" in response_data and response_data["failed"]:
                failed_info = response_data["failed"][0]
                error = failed_info.get("error", "Unknown error")
                logger.error(f"Job import failed: {error}")
                return "N/A"
            else:
                logger.warning("Could not extract permalink from response")
                return "N/A"
        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"Error parsing response for permalink: {e}")
            return "N/A"
