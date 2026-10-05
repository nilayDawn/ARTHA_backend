from pathlib import Path
from typing import Any

TEMPLATES_DIR = Path(__file__).resolve().parent


def render_email_template(template_name: str, context: dict[str, Any]) -> str:
    """
    Renders an HTML email template with basic string/key substitution.
    Supports {{ variable }} replacement syntax.
    """
    template_path = TEMPLATES_DIR / "emails" / template_name
    if not template_path.is_file():
        raise FileNotFoundError(f"Template '{template_name}' not found at {template_path}")

    content = template_path.read_text(encoding="utf-8")
    for key, value in context.items():
        placeholder = f"{{{{ {key} }}}}"
        content = content.replace(placeholder, str(value if value is not None else ""))
        placeholder_no_space = f"{{{{{key}}}}}"
        content = content.replace(placeholder_no_space, str(value if value is not None else ""))

    return content
