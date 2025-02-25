import logging
from flask import Blueprint, render_template, Response
from flask_login import login_required
from helpers.decorators import staff_required, approved_required
from models.ecoregions import Ecoregion

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

ecoregions_bp = Blueprint("ecoregions", __name__)


@ecoregions_bp.route("/ecoregions/view_all", endpoint="view_ecoregions")
@login_required
@approved_required
@staff_required
def view_ecoregions():
    all_ecoregions = Ecoregion.get_counts()
    return render_template("ecoregions.html", ecoregions=all_ecoregions)


@ecoregions_bp.route("/ecoregions/download", endpoint="download_ecoregions")
@login_required
@approved_required
@staff_required
def download_ecoregions():
    all_ecoregions = Ecoregion.get_counts()
    # Define CSV headers
    fieldnames = [
        "ecoregion_name",
        "num_sequencing_samples",
        "num_external_samples_ITS",
        "num_external_samples_SSU",
    ]

    # Create CSV data
    csv_data = []
    for ecoregion in all_ecoregions:
        csv_data.append(
            {
                "ecoregion_name": ecoregion.ecoregion_name,
                "num_sequencing_samples": ecoregion.num_sequencing_samples,
                "num_external_samples_ITS": ecoregion.num_external_samples_ITS,
                "num_external_samples_SSU": ecoregion.num_external_samples_SSU,
            }
        )

    # Generate CSV response
    def generate():
        yield ",".join(fieldnames) + "\n"  # Header row
        for row in csv_data:
            yield ",".join([str(row[field]) for field in fieldnames]) + "\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=ecoregions.csv"},
    )
