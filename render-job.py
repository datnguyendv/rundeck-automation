import yaml
import json
import argparse
import sys
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import re


def parse_arguments():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Render Rundeck job from Jinja template")
    parser.add_argument("--template", required=True, help="Template filename (e.g. job-base.j2)")
    parser.add_argument("--data", required=True, help="JSON string containing job data")
    parser.add_argument("--output", required=False, help="Output file path (optional, defaults to stdout or auto-generated)")
    return parser.parse_args()


def load_job_data(data_string: str) -> dict:
    """Load and validate JSON data."""
    try:
        data = json.loads(data_string)
        if not isinstance(data, dict):
            raise ValueError("Data must be a JSON object")
        return data
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON data: {str(e)}", file=sys.stderr)
        raise


def render_template(template_name: str, data: dict, template_dir: Path) -> str:
    """Render Jinja2 template with data."""
    try:
        if not template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {template_dir}")
        
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        
        template = env.get_template(template_name)
        output = template.render(**data)
        
        return output
    
    except Exception as e:
        print(f"❌ Error rendering template '{template_name}': {str(e)}", file=sys.stderr)
        raise


def generate_safe_filename(name: str) -> str:
    """Generate safe filename from job name."""
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip().lower())
    return f"{safe_name}.yaml"


def write_output(content: str, output_path: Path = None) -> None:
    """Write rendered content to file or stdout."""
    try:
        if output_path:
            # Write to specified file
            output_path.parent.mkdir(exist_ok=True, parents=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ Generated Rundeck job file: {output_path}", file=sys.stderr)
        else:
            # Write to stdout
            print(content)
    
    except IOError as e:
        print(f"❌ Error writing output: {str(e)}", file=sys.stderr)
        raise


def main():
    """Main execution flow."""
    try:
        # --- Parse arguments ---
        args = parse_arguments()
        
        # --- Setup paths ---
        BASE_DIR = Path(__file__).resolve().parent
        TEMPLATE_DIR = BASE_DIR / "template"
        
        # --- Load data ---
        data = load_job_data(args.data)
        
        # --- Render template ---
        output = render_template(args.template, data, TEMPLATE_DIR)
        
        # --- Determine output path ---
        if args.output:
            # Use specified output path
            output_path = Path(args.output)
        else:
            # If no output specified, write to stdout
            output_path = None
        
        # --- Write output ---
        print(output_path)
        write_output(output, output_path)
        
        return 0
    
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

