from flask import Blueprint, current_app, render_template

from app.landing.copy import COPY

landing_bp = Blueprint("landing", __name__, template_folder="templates")


@landing_bp.get("/")
def index():
    t = COPY.get(current_app.config.get("UI_LOCALE", "en"), COPY["en"])
    return render_template("index.html", t=t)
