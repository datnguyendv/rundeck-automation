"""
Script import secrets vào Vault
"""
import argparse
import os
import json
import sys
import requests
from pathlib import Path
from typing import List, Dict, Optional

from utils import TemplateRenderer


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Generate and import secrets into Vault")
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Comma-separated list of secret keys to include (e.g. GITHUB_TOKEN,NPM_TOKEN,GCP_CREDS)"
    )
    parser.add_argument(
        "--vault-addr",
        default=os.environ.get("VAULT_ADDR", "https://vault.example.com"),
        help="Vault address (default: from VAULT_ADDR env)"
    )
    parser.add_argument(
        "--vault-path",
        default=os.environ.get("VAULT_PATH", "secret/data/dev"),
        help="Vault path (default: from VAULT_PATH env)"
    )
    parser.add_argument(
        "--vault-token",
        default=os.environ.get("RD_OPTION_VAULTTOKEN"),
        help="Vault token (default: from Rundeck option RD_OPTION_VAULTTOKEN)"
    )
    return parser.parse_args()


def parse_input_keys(input_string: str) -> List[str]:
    """Parse comma-separated input keys"""
    keys = [k.strip() for k in input_string.split(",") if k.strip()]
    print(f"[INFO] Parsed {len(keys)} keys: {', '.join(keys)}")
    return keys


def get_rundeck_variables() -> Dict[str, str]:
    """Get configuration from Rundeck environment variables"""
    config = {
        "env": os.environ.get("RD_OPTION_ENV", "dev"),
        "vault_name": os.environ.get("RD_OPTION_VAULTNAME", "default-service"),
        "namespace": os.environ.get("RD_OPTION_NAMESPACE", "default"),
        "action": os.environ.get("RD_OPTION_ACTION", "create"),
        "job_id": os.environ.get("RD_JOB_ID", "default"),
        "exec_id": os.environ.get("RD_JOB_EXECID", "0")
    }
    return config


def generate_vault_gke_yaml(vault_keys: List[str], config: Dict[str, str]) -> Optional[str]:
    """Generate vault-gke YAML config from Jinja2 template"""
    try:
        base_dir = Path(__file__).resolve().parent
        template_dir = base_dir / "template"
        
        if not template_dir.exists():
            print(f"⚠️ [WARN] Template directory not found: {template_dir}", file=sys.stderr)
            return None
        
        # Prepare template data
        template_data = {
            "ENV": config["env"],
            "vault_name": config["vault_name"],
            "namespace": config["namespace"],
            "action": config["action"],
            "vault_keys": vault_keys
        }
        
        print("\n# ---------------- YAML GENERATION START ----------------")
        print(f"# Environment: {config['env']}")
        print(f"# Vault Name: {config['vault_name']}")
        print(f"# Namespace: {config['namespace']}")
        print(f"# Action: {config['action']}")
        print(f"# Keys: {', '.join(vault_keys)}")
        
        # Render template using TemplateRenderer
        renderer = TemplateRenderer(template_dir=template_dir)
        rendered_yaml = renderer.render("vault-gke.j2", template_data)
        
        print(f"# Generated YAML:\n{rendered_yaml}")
        
        # Save to file
        output_dir = Path(f"/tmp/{config['job_id']}")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"vault-gke-{config['exec_id']}.yaml"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(rendered_yaml)
        
        print(f"# ✅ YAML saved to: {output_file}")
        print("# ---------------- YAML GENERATION END ------------------\n")
        
        return rendered_yaml
    
    except Exception as e:
        print(f"⚠️ [WARN] Failed to generate YAML: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def gather_secret_data(keys: List[str]) -> Dict[str, str]:
    """Gather secret values from Rundeck environment variables"""
    data_dict = {}
    missing_keys = []
    
    for key in keys:
        env_key = f"RD_OPTION_{key}"
        value = os.environ.get(env_key)
        
        if value is None:
            print(f"[WARN] Missing environment variable: {env_key}", file=sys.stderr)
            missing_keys.append(key)
            value = ""
        
        data_dict[key] = value
    
    if missing_keys:
        print(f"[WARN] Total missing keys: {len(missing_keys)}", file=sys.stderr)
    
    return data_dict


def prepare_vault_payload(data_dict: Dict[str, str]) -> str:
    """Prepare Vault KV v2 payload"""
    vault_payload = {"data": data_dict}
    json_payload = json.dumps(vault_payload, indent=2)
    return json_payload


def import_to_vault(vault_addr: str, vault_path: str, vault_token: str, json_payload: str) -> bool:
    """Import secrets to Vault via API"""
    print("# ---------------- VAULT IMPORT START ----------------")
    print(f"# Vault Addr: {vault_addr}")
    print(f"# Vault Path: {vault_path}")
    print(f"# Payload:\n{json_payload}")
    print("# ----------------------------------------------------")
    
    if not vault_token:
        print("[ERROR] Missing Vault token. Provide via --vault-token or RD_OPTION_VAULTTOKEN", file=sys.stderr)
        return False
    
    url = f"{vault_addr}/v1/{vault_path}"
    headers = {
        "X-Vault-Token": vault_token,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, data=json_payload, timeout=30)
        print(f"\n[INFO] Vault API response: {response.status_code}")
        
        if response.status_code in [200, 204]:
            print("[SUCCESS] Secrets successfully imported into Vault.")
            return True
        else:
            print(f"[ERROR] Vault response body: {response.text}", file=sys.stderr)
            return False
    
    except requests.exceptions.Timeout:
        print(f"[ERROR] Request timeout: Vault did not respond in time", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to connect to Vault: {e}", file=sys.stderr)
        return False


def main():
    """Main execution flow"""
    try:
        print("=" * 80)
        print("🚀 Vault Secret Manager - Starting")
        print("=" * 80)
        
        args = parse_arguments()
        keys = parse_input_keys(args.input)
        config = get_rundeck_variables()
        
        # Generate YAML (if template exists)
        generate_vault_gke_yaml(keys, config)
        
        # Gather secret data
        data_dict = gather_secret_data(keys)
        
        # Prepare Vault payload
        json_payload = prepare_vault_payload(data_dict)
        
        # Import to Vault
        success = import_to_vault(
            vault_addr=args.vault_addr,
            vault_path=args.vault_path,
            vault_token=args.vault_token,
            json_payload=json_payload
        )
        
        if success:
            print("\n" + "=" * 80)
            print("✅ All operations completed successfully!")
            print("=" * 80)
            sys.exit(0)
        else:
            print("\n" + "=" * 80)
            print("❌ Operation failed!")
            print("=" * 80)
            sys.exit(1)
    
    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ Fatal error occurred!")
        print("=" * 80)
        print(f"[ERROR] {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
