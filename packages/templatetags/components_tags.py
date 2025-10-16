from django import template

# Proxy to src.components.templatetags.components_tags if present
try:
    from src.components.templatetags.components_tags import *  # noqa: F401,F403,F401
except Exception:
    register = template.Library()
