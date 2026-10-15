"""Minimal i18n. Templates and code write the English text directly:
    {{ _("Pending approvals") }}
and the German catalog (app/i18n_de.py) maps English -> German. UI_LOCALE=en
(default) or de selects the language for the whole deployment. A missing
German entry falls back to the English text rather than breaking a page.

Prose-heavy pages are localized as whole files instead: `landing.html` is
English and `landing.de.html` the German original; localized("landing.html")
returns the candidate list for render_template."""

from flask import current_app


def _catalog() -> dict:
    from app.i18n_de import DE
    return DE


def translate(text: str, **kwargs) -> str:
    if current_app.config.get("UI_LOCALE", "en") == "de":
        text = _catalog().get(text, text)
    return text.format(**kwargs) if kwargs else text


def localized(template_name: str) -> list[str]:
    if current_app.config.get("UI_LOCALE", "en") == "de":
        return [template_name.replace(".html", ".de.html"), template_name]
    return [template_name]


def init_app(app) -> None:
    app.jinja_env.globals["_"] = translate
