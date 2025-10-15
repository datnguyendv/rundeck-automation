"""
Script create Rundeck job for SWE input vault keys
"""
import os
import json
from pathlib import Path
from typing import Dict

from utils import TemplateRenderer, RundeckClient, send_to_slack

def generate_job_data(job_id: str, execution_id: str) -> Dict:
    """Generate job data from environment variables"""
    try:
        vault_name = os.getenv("RD_OPTION_VAULTNAME", "test")
        namespace = os.getenv("RD_OPTION_NAMESPACE", "default")
        action = os.getenv("RD_OPTION_ACTION", "create")
        job_name = f"{action} vault value for {vault_name}"
        vault_keys_raw = os.getenv("RD_OPTION_VAULTKEY", "NPM_TOKEN,GCP")
        vault_keys = [k.strip() for k in vault_keys_raw.split(",") if k.strip()]
        
        result = {
            "options": [],
            "group": "approval",
            "name": job_name,
            "keys": vault_keys_raw,
            "job_id": job_id,
            "execution_uuid": execution_id,
        }
        
        # Add options
        result["options"].append({"name": "VaultName", "description": "", "value": vault_name})
        result["options"].append({"name": "namespace", "description": "", "value": namespace})
        result["options"].append({"name": "Action", "description": "", "value": action})
        
        # VaultToken
        result["options"].append({
            "name": "VaultToken",
            "description": "",
            "required": True,
            "hidden": True,
            "secure": True,
            "storagePath": "keys/project/vaul-v1/Token",
            "valueExposed": True
        })
        
        # Add each VaultKey
        for key in vault_keys:
            result["options"].append({
                "name": key,
                "description": f"Enter value for key {key}",
                "required": True
            })
        
        print("🧩 Generated input data:")
        print(json.dumps(result, indent=4))
        return result
    
    except Exception as e:
        print(f"❌ Error generating job data: {str(e)}")
        raise


def main() -> None:
    try:
        print("=" * 60)
        print("🚀 Starting Rundeck Job Creation Process")
        print("=" * 60)
        
        # Get environment variables
        job_id = os.getenv("RD_JOB_ID", "jobid")
        execution_uuid = os.getenv("RD_JOB_EXECUTIONUUID", "execuuid")
        exec_id = os.getenv("RD_JOB_EXECID", "123")
        user = os.getenv("RD_JOB_USERNAME", "unknown")
        
        print(f"📋 Job ID: {job_id}")
        print(f"📋 Execution UUID: {execution_uuid}")
        print(f"📋 Exec ID: {exec_id}")
        print(f"👤 User: {user}")
        
        # Setup paths
        base_dir = Path(__file__).resolve().parent
        output_dir = Path(f"/tmp/{job_id}/{execution_uuid}")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"approval_job_{exec_id}.yaml"
        
        print(f"📁 Output directory: {output_dir}")
        print(f"📄 Output file: {output_file}")
        
        # Step 1: Generate job data
        print("\n" + "=" * 60)
        print("Step 1: Generating job data...")
        print("=" * 60)
        data = generate_job_data(job_id, execution_uuid)
        job_name = data["name"]
        
        # Step 2: Render template
        print("\n" + "=" * 60)
        print("Step 2: Rendering job template...")
        print("=" * 60)
        renderer = TemplateRenderer(template_dir=base_dir / "template")
        renderer.render_to_file("vault-value.j2", data, output_file)
        
        # Step 3: Import to Rundeck
        print("\n" + "=" * 60)
        print("Step 3: Importing job to Rundeck...")
        print("=" * 60)
        rundeck = RundeckClient()
        response_data = rundeck.import_job(output_file)
        job_link = rundeck.get_job_permalink(response_data)
        
        # Step 4: Send Slack notification
        print("\n" + "=" * 60)
        print("Step 4: Sending Slack notification...")
        print("=" * 60)
        send_to_slack(job_name, job_link, user)
        
        print("\n" + "=" * 60)
        print("ALL STEPS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
    
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ PROCESS FAILED!")
        print("=" * 60)
        print(f"Error: {str(e)}")
        raise


if __name__ == "__main__":
    main()
