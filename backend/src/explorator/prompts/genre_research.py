"""Markdown-based prompt loader for genre research agent."""

from pathlib import Path


def load_prompt(template_name: str, **kwargs: str) -> str:
    """Load an MD prompt template and inject variables via str.replace().

    Uses str.replace() instead of str.format() to avoid breakage when
    templates or injected variables contain literal { / } characters.
    """
    path = Path(__file__).parent / "genre_research" / f"{template_name}.md"
    template = path.read_text()
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))
    return template
