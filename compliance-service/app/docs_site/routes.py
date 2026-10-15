from flask import Blueprint, abort, render_template

docs_bp = Blueprint("docs", __name__, url_prefix="/docs", template_folder="templates")

PAGES = [
    ("overview", "Overview and your path"),
    ("quickstart", "Quickstart (15 minutes)"),
    ("api", "API reference"),
    ("agent", "The AI agent and webhooks"),
    ("go-live", "Going live checklist"),
]
_SLUGS = {slug for slug, _ in PAGES}


@docs_bp.get("/", defaults={"page": "overview"})
@docs_bp.get("/<page>")
def page(page):
    if page not in _SLUGS:
        abort(404)
    title = dict(PAGES)[page]
    return render_template(f"docs/{page.replace('-', '_')}.html", pages=PAGES, current=page, title=title)
