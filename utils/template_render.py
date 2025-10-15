"""
Module render Jinja2 templates
"""
import re
from pathlib import Path
from typing import Dict, Optional
from jinja2 import Environment, FileSystemLoader


class TemplateRenderer:
    def __init__(self, template_dir: Optional[Path] = None):
        if template_dir is None:
            # Default to template/ trong cùng thư mục với script gọi
            self.template_dir = Path.cwd() / "template"
        else:
            self.template_dir = Path(template_dir)
        
        if not self.template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {self.template_dir}")
        
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    
    def render(self, template_name: str, data: Dict) -> str:
        """
        Render template với data
        Returns: Rendered string
        """
        try:
            template = self.env.get_template(template_name)
            output = template.render(**data)
            return output
        except Exception as e:
            raise RuntimeError(f"Error rendering template '{template_name}': {str(e)}")
    
    def render_to_file(self, template_name: str, data: Dict, output_path: Path) -> Path:
        """
        Render template và ghi ra file
        Returns: Path to output file
        """
        output = self.render(template_name, data)
        
        # Create parent directories if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output)
        
        print(f"✅ Generated file: {output_path}")
        return output_path
    
    @staticmethod
    def generate_safe_filename(name: str, extension: str = "yaml") -> str:
        """Generate safe filename from job name"""
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip().lower())
        return f"{safe_name}.{extension}"

