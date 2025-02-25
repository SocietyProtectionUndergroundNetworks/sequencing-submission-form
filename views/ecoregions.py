import logging
from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from models.ecoregions import Ecoregion
from helpers.decorators import (
    admin_or_owner_required,
    approved_required,
)

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

ecoregions_bp = Blueprint("ecoregions", __name__)


@ecoregions_bp.route("/ecoregions/view_all")
@login_required
def data():
    all_ecoregions = Ecoregion.get_counts()

    return render_template("ecoregions.html", ecoregions=all_ecoregions)
