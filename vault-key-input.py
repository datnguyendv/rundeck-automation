import os
import json
import subprocess
import requests
from pathlib import Path
from typing import Dict


def generate_job_data(job_id: str, execution_id: str) -> Dict:
    try:
        vault_name = os.getenv("RD_OPTION_VAULTNAME", "test")
        namespace = os.getenv("RD_OPTION_NAMESPACE", "default")
        action = os.getenv("RD_OPTION_ACTION", "create")
        job_name = action + " vault value for " + vault_name
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

        # --- Add options ---
        result["options"].append({"name": "VaultName", "description": "", "value": vault_name})
        result["options"].append({"name": "namespace", "description": "", "value": namespace})
        result["options"].append({"name": "Action", "description": "", "value": action})

        # --- VaultToken ---
        result["options"].append({
            "name": "VaultToken",
            "description": "",
            "required": True,
            "hidden": True,
            "secure": True,
            "storagePath": "keys/project/vaul-v1/Token",
            "valueExposed": True
        })

        # --- Add each VaultKey ---
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


def render_job_template(data: Dict, output_file: Path, template_name: str = "vault-value.j2") -> None:
    """Gọi render-job.py để render template thành file YAML."""
    try:
        base_dir = Path(__file__).resolve().parent
        render_script = base_dir / "render-job.py"

        if not render_script.exists():
            raise FileNotFoundError(f"Render script not found: {render_script}")

        cmd = [
            "python3",
            str(render_script),
            "--template", template_name,
            "--data", json.dumps(data),
            "--output", str(output_file)
        ]

        print(f"🚀 Running render-job.py with template '{template_name}'...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        if result.stdout:
            print(result.stdout)
        
        print(f"✅ Template rendered successfully to {output_file}")
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running render-job.py: {str(e)}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error in render_job_template: {str(e)}")
        raise


def import_job_to_rundeck(output_file: Path) -> None:
    """Import job YAML vào Rundeck thông qua API sử dụng requests."""
    try:
        rundeck_token = os.getenv("RD_TOKEN", "Vczci5ltVL6coadjTQyemtAmML9lNJLU")
        rundeck_url = os.getenv("RD_URL", "http://rundeck:4440")
        project_name = os.getenv("RD_PROJECT", "vault-management")

        if not output_file.exists():
            raise FileNotFoundError(f"Output file not found: {output_file}")

        with open(output_file, 'r') as f:
            yaml_content = f.read()

        url = f"{rundeck_url}/api/41/project/{project_name}/jobs/import"
        headers = {
            "X-Rundeck-Auth-Token": rundeck_token,
            "Content-Type": "application/yaml"
        }

        print(f"📤 Importing job to Rundeck from {output_file}...")
        print(f"   URL: {url}")

        response = requests.post(url, headers=headers, data=yaml_content, timeout=30)
        response.raise_for_status()
        
        print("✅ Job imported successfully!")
        print(f"   Status Code: {response.status_code}")
        
        try:
            response_data = response.json()
            print(f"   Response: {json.dumps(response_data, indent=2)}")
        except json.JSONDecodeError:
            print(f"   Response: {response.text[:500]}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {str(e)}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error importing job to Rundeck: {str(e)}")
        raise


def main() -> None:
    """Main flow: generate -> render -> import"""
    try:
        print("=" * 60)
        print("🚀 Starting Rundeck Job Creation Process")
        print("=" * 60)

        # Get environment variables
        job_id = os.getenv("RD_JOB_ID", "jobid")
        execution_uuid = os.getenv("RD_JOB_EXECUTIONUUID", "execuuid")
        exec_id = os.getenv("RD_JOB_EXECID", "123")

        print(f"📋 Job ID: {job_id}")
        print(f"📋 Execution UUID: {execution_uuid}")
        print(f"📋 Exec ID: {exec_id}")

        output_dir = Path(f"/tmp/{job_id}/{execution_uuid}")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"approval_job_{exec_id}.yaml"

        print(f"📁 Output directory: {output_dir}")
        print(f"📄 Output file: {output_file}")

        # --- Step 1: Generate data  ---
        print("\n" + "=" * 60)
        print("Step 1: Generating job data...")
        print("=" * 60)
        data = generate_job_data(job_id, execution_uuid)

        # --- Step 2: Render template ---
        print("\n" + "=" * 60)
        print("Step 2: Rendering job template...")
        print("=" * 60)
        render_job_template(data, output_file)

        # --- Step 3: Import to Rundeck ---
        print("\n" + "=" * 60)
        print("Step 3: Importing job to Rundeck...")
        print("=" * 60)
        import_job_to_rundeck(output_file)

        print("\n" + "=" * 60)
        print("✅ ALL STEPS COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ PROCESS FAILED!")
        print("=" * 60)
        print(f"Error: {str(e)}")
        raise


if __name__ == "__main__":
    main()

