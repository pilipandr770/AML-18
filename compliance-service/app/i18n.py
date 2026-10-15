"""Minimal i18n. Templates and code write the English text directly:
    {{ _("Pending approvals") }}
and the German catalog maps English -> German. UI_LOCALE=en (default) or
de selects the language for the whole deployment; a missing German entry
falls back to the English text rather than breaking the page."""

from flask import current_app

DE: dict[str, str] = {}


def register_german(entries: dict[str, str]) -> None:
    DE.update(entries)


def translate(text: str, **kwargs) -> str:
    if current_app.config.get("UI_LOCALE", "en") == "de":
        text = DE.get(text, text)
    return text.format(**kwargs) if kwargs else text


def init_app(app) -> None:
    app.jinja_env.globals["_"] = translate
