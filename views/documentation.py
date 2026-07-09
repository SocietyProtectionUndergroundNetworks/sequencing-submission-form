import logging
import os
from flask_login import login_required
from flask import (
    Blueprint,
    render_template,
    jsonify,
    send_file,
    make_response,
    Response,
)
from pathlib import Path
from helpers.create_xls_template import create_template_one_drive_and_excel
from helpers.metadata_check import get_columns_data
from helpers.decorators import (
    approved_required,
    admin_required,
)

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

documentation_bp = Blueprint("documentation", __name__)


@documentation_bp.route("/robots.txt", endpoint="robots_txt")
def robots_txt():
    return Response(
        "User-agent: *\nDisallow: /mobile_app_instructions\n",
        mimetype="text/plain",
    )


@documentation_bp.route(
    "/mobile_app_instructions",
    endpoint="mobile_app_instructions",
)
def mobile_app_instructions():
    response = make_response(
        render_template(
            "mobile_app_instructions.html",
            play_link=os.environ.get("RESEARCHER_GUIDE_PLAY_LINK", ""),
            support_email=os.environ.get("RESEARCHER_GUIDE_SUPPORT_EMAIL", ""),
        )
    )
    # Not linked from anywhere crawlable; belt-and-suspenders alongside
    # the robots.txt disallow above for crawlers that ignore it.
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@documentation_bp.route(
    "/metadata_instructions",
    endpoint="metadata_instructions",
)
def metadata_instructions():
    expected_columns = get_columns_data(exclude=True)
    google_sheets_template_url = os.environ.get("GOOGLE_SPREADSHEET_TEMPLATE")

    return render_template(
        "metadata_instructions.html",
        expected_columns=expected_columns,
        google_sheets_template_url=google_sheets_template_url,
    )


@documentation_bp.route("/xls_sample", endpoint="xls_sample")
def xls_sample():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = Path(project_root, "static", "xls")
    xls_path = path / "template_with_dropdowns_for_one_drive_and_excel.xlsx"

    return send_file(xls_path, as_attachment=True)


@documentation_bp.route(
    "/create_xls_template",
    endpoint="create_xls_template",
)
@login_required
@admin_required
@approved_required
def create_xls_template():
    create_template_one_drive_and_excel()

    return (jsonify({"result": 1}), 200)
