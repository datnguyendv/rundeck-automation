"""
Module tương tác với Rundeck API
"""
import os
import json
from pathlib import Path
from typing import Dict, Optional
import requests


class RundeckClient:
    def __init__(
        self, 
        url: Optional[str] = None, 
        token: Optional[str] = None,
        project: Optional[str] = None
    ):
        self.url = url or os.getenv("RD_URL", "http://localhost:4440")
        self.token = token or os.getenv("RD_TOKEN","Vczci5ltVL6coadjTQyemtAmML9lNJLU")
        self.project = project or os.getenv("RD_PROJECT", "vault-management")
        
        if not self.token:
            raise ValueError("Rundeck token not provided (RD_TOKEN)")
    
    def import_job(self, yaml_file: Path) -> Dict:
        """
        Import job từ YAML file vào Rundeck
        Returns: Dict chứa response data
        """
        if not yaml_file.exists():
            raise FileNotFoundError(f"YAML file not found: {yaml_file}")
        
        with open(yaml_file, 'r', encoding='utf-8') as f:
            yaml_content = f.read()
        
        url = f"{self.url}/api/54/project/{self.project}/jobs/import"
        headers = {
            "X-Rundeck-Auth-Token": self.token,
            "Content-Type": "application/yaml"
        }
        
        print(f"📤 Importing job to Rundeck from {yaml_file.name}...")
        print(f"   URL: {url}")
        
        try:
            response = requests.post(url, headers=headers, data=yaml_content, timeout=30)
            response.raise_for_status()
            
            print("✅ Job imported successfully!")
            print(f"   Status Code: {response.status_code}")
            
            response_data = response.json()
            print(f"   Response: {json.dumps(response_data, indent=2)}")
            
            return response_data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Request error: {str(e)}")
            raise
    
    def get_job_permalink(self, response_data: Dict) -> str:
        """
        Extract permalink từ response data
        Returns: Permalink string hoặc 'N/A'
        """
        if "succeeded" in response_data and len(response_data["succeeded"]) > 0:
            job_info = response_data["succeeded"][0]
            permalink = job_info.get("permalink") or job_info.get("href") or "N/A"
            print(f"🔗 Job Permalink: {permalink}")
            return permalink
        else:
            print("⚠️ Could not find job permalink in response.")
            return "N/A"

