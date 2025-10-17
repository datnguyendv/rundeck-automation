import re
import logging
import json
import time
import requests
from pathlib import Path
from typing import Dict, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import RundeckAPIError
from .logger import setup_logger

logger = setup_logger(__name__)

class RundeckClient:
    def __init__(
        self,
        url: str,
        token: str,
        project: str,
        timeout: int = 30,
        max_retries: int = 3
    ):
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
        return {
            "X-Rundeck-Auth-Token": self.token,
            "Content-Type": content_type,
            "Accept": "application/json"
        }
    
    def import_job(self, yaml_file: Path, duplicate_option: str = "update") -> Dict:
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
        try:
            if "succeeded" in response_data and response_data["succeeded"]:
                job_info = response_data["succeeded"][0]
                permalink = job_info.get("permalink") or job_info.get("href", "N/A")
                logger.info(f"🔗 Job permalink: {permalink}")
                print(f"href: {permalink}")
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
    def delete_job(self, job_id: str) -> bool:
        url = f"{self.url}/api/54/job/{job_id}"
        
        logger.info(f"🗑️  Deleting Rundeck job: {job_id}")
        
        try:
            response = self.session.delete(
                url,
                headers=self._get_headers("application/json"),
                timeout=self.timeout
            )
            
            if response.status_code == 204:
                logger.info(f"✅ Job {job_id} deleted successfully")
                return True
            elif response.status_code == 404:
                logger.warning(f"⚠️ Job {job_id} not found (may already be deleted)")
                return False
            else:
                response.raise_for_status()
                return False
        
        except requests.exceptions.HTTPError as e:
            error_msg = f"Failed to delete job {job_id}: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {json.dumps(error_detail)}"
            except:
                error_msg += f" - {e.response.text}"
            logger.error(error_msg)
            raise RundeckAPIError(error_msg)
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed while deleting job: {str(e)}"
            logger.error(error_msg)
            raise RundeckAPIError(error_msg)


    def delete_job_by_href(self, href: str) -> bool:
        patterns = [
            r'/job/show/([a-f0-9-]+)',  # Standard show URL
            r'/job/([a-f0-9-]+)',        # Direct job ID
            r'id=([a-f0-9-]+)',          # Query parameter
        ]
        
        job_id = None
        for pattern in patterns:
            match = re.search(pattern, href)
            if match:
                job_id = match.group(1)
                break
        
        if not job_id:
            # If no pattern matches, assume the href IS the job ID
            job_id = href.split('/')[-1]
        
        logger.info(f"Extracted job ID: {job_id} from href: {href}")
        return self.delete_job(job_id)
