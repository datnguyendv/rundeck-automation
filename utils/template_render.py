import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, TemplateError, TemplateNotFound

from .exceptions import TemplateRenderError
from .logger import setup_logger

logger = setup_logger(__name__)


class TemplateRenderer:
    def __init__(self, template_dir: Optional[Path] = None):
        if template_dir is None:
            self.template_dir = Path.cwd() / "template"
        else:
            self.template_dir = Path(template_dir)
        
        if not self.template_dir.exists():
            raise TemplateRenderError(f"Template directory not found: {self.template_dir}")
        
        logger.info(f"Initialized TemplateRenderer with directory: {self.template_dir}")
        
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,  # Better for YAML files
        )
    
    def validate_template_exists(self, template_name: str) -> None:
        template_path = self.template_dir / template_name
        if not template_path.exists():
            available_templates = [f.name for f in self.template_dir.glob("*.j2")]
            raise TemplateRenderError(
                f"Template '{template_name}' not found. "
                f"Available templates: {', '.join(available_templates)}"
            )
    
    def render(self, template_name: str, data: Dict[str, Any]) -> str:
        try:
            logger.info(f"Rendering template: {template_name}")
            logger.debug(f"Template data keys: {list(data.keys())}")
            
            self.validate_template_exists(template_name)
            
            template = self.env.get_template(template_name)
            output = template.render(**data)
            
            logger.info(f"✅ Template rendered successfully ({len(output)} chars)")
            return output
            
        except TemplateNotFound as e:
            raise TemplateRenderError(f"Template not found: {e}")
        except TemplateError as e:
            raise TemplateRenderError(f"Template syntax error: {e}")
        except Exception as e:
            raise TemplateRenderError(f"Unexpected error rendering template: {e}")
    
    def render_to_file(
        self,
        template_name: str,
        data: Dict[str, Any],
        output_path: Path,
        overwrite: bool = True
    ) -> Path:
        if output_path.exists() and not overwrite:
            raise TemplateRenderError(f"Output file already exists: {output_path}")
        
        output = self.render(template_name, data)
        
        try:
            # Create parent directories
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(output)
            
            logger.info(f"✅ Output written to: {output_path}")
            return output_path
            
        except IOError as e:
            raise TemplateRenderError(f"Failed to write output file: {e}")
    
    @staticmethod
    def generate_safe_filename(name: str, extension: str = "yaml") -> str:
        # Remove/replace unsafe characters
        safe_name = re.sub(r'[^\w\s-]', '', name.strip().lower())
        safe_name = re.sub(r'[-\s]+', '-', safe_name)
        safe_name = safe_name[:200]  # Limit length
        
        return f"{safe_name}.{extension}"
