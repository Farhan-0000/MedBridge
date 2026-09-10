"""Frontend Presentation Components Package (TASK-26, Module M-20)."""
from medbridge.frontend.components.chat import (
    ACTION_BADGE_CONFIG,
    get_action_badge_html,
    render_action_badge,
    render_chat_message,
)
from medbridge.frontend.components.citations import render_citations_panel
from medbridge.frontend.components.disclaimer import (
    DISCLAIMER_TEXT,
    render_disclaimer,
)
from medbridge.frontend.components.sidebar import render_sidebar

__all__ = [
    "render_disclaimer",
    "DISCLAIMER_TEXT",
    "render_action_badge",
    "get_action_badge_html",
    "render_chat_message",
    "ACTION_BADGE_CONFIG",
    "render_citations_panel",
    "render_sidebar",
]
