from flask import Blueprint, render_template

legal_bp = Blueprint("legal", __name__, template_folder="templates")


@legal_bp.get("/impressum")
def impressum():
    return render_template("impressum.html")


@legal_bp.get("/datenschutz")
def datenschutz():
    return render_template("datenschutz.html")
