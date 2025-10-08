import argparse
import os
import json
import sys
import requests

def main():
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
    args = parser.parse_args()

    # Parse input keys
    keys = [k.strip() for k in args.input.split(",") if k.strip()]

    # Gather Rundeck environment variables
    data_dict = {}
    for key in keys:
        env_key = f"RD_OPTION_{key}"
        value = os.environ.get(env_key)
        if value is None:
            print(f"[WARN] Missing environment variable: {env_key}", file=sys.stderr)
            value = ""
        data_dict[key] = value

    # Vault KV v2 thường yêu cầu payload dạng {"data": {...}}
    json_payload = json.dumps(data_dict, indent=2)

    # In ra payload trước khi gửi (để debug)
    print("# ---------------- VAULT IMPORT START ----------------")
    print(f"# Vault Addr: {args.vault_addr}")
    print(f"# Vault Path: {args.vault_path}")
    print(f"# Payload:\n{json_payload}")
    print("# ----------------------------------------------------")

    # Kiểm tra token
    if not args.vault_token:
        print("[ERROR] Missing Vault token. Provide via --vault-token or RD_OPTION_VAULTTOKEN", file=sys.stderr)
        sys.exit(1)

    # Thực thi POST request
    url = f"{args.vault_addr}/v1/{args.vault_path}"
    headers = {
        "X-Vault-Token": args.vault_token,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, data=json_payload, timeout=10)
        print(f"\n[INFO] Vault API response: {response.status_code}")
        if response.status_code != 200 and response.status_code != 204:
            print(f"[ERROR] Vault response body: {response.text}")
        else:
            print("[SUCCESS] Secrets successfully imported into Vault.")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to connect to Vault: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
