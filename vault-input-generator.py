import os, json, subprocess
from pathlib import Path

# --- Generate data ---
job_name = "Add vault value for execution " + os.getenv("RD_JOB_EXECID", "123")
vault_name = os.getenv("RD_OPTION_VAULTNAME", "test")
namespace = os.getenv("RD_OPTION_NAMESPACE", "default")
action = os.getenv("RD_OPTION_ACTION", "create")
vault_keys_raw = os.getenv("RD_OPTION_VAULTKEY", "NPM_TOKEN,GCP")

vault_keys = [k.strip() for k in vault_keys_raw.split(",") if k.strip()]

result = {"options": [], "group": "approval", "name": job_name, "key": vault_keys_raw}

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

# --- Print JSON for debug ---
print("🧩 Generated input data:")
print(json.dumps(result, indent=4))

# --- Call render-job.py ---
BASE_DIR = Path(__file__).resolve().parent
render_script = BASE_DIR / "render-job.py"
template_name = "vault-value.j2"  # bạn có thể đổi theo tên file template mong muốn

cmd = [
    "python3",
    str(render_script),
    "--template", template_name,
    "--data", json.dumps(result)
]
print(cmd)

print(f"🚀 Running render-job.py with template '{template_name}'...")
subprocess.run(cmd, check=True)

