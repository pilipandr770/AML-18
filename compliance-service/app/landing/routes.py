from flask import Blueprint, render_template

landing_bp = Blueprint("landing", __name__, template_folder="templates")


@landing_bp.get("/")
def index():
    return render_template("index.html")
