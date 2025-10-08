import yaml
import json
import argparse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import re

# --- CLI arguments ---
parser = argparse.ArgumentParser(description="Render Rundeck job from Jinja template")
parser.add_argument("--template", required=True, help="Template filename (e.g. job-base.j2)")
parser.add_argument("--data", required=True, help="JSON string containing job data")
args = parser.parse_args()

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "template"
OUTPUT_DIR = BASE_DIR / "projects" / "vault"

# --- Load data from argument ---
data = json.loads(args.data)

# --- Jinja Environment ---
env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

template = env.get_template(args.template)

# --- Render template ---
output = template.render(**data)

# --- Generate job name safely ---
raw_name = data.get("name", "rundeck-job")
safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw_name.strip().lower())
output_path = OUTPUT_DIR / f"{safe_name}.yaml"

# --- Write output file ---
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
with open(output_path, "w") as f:
    f.write(output)

print(f"✅ Generated Rundeck job file: {output_path}")
