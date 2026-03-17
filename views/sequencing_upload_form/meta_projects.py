from . import upload_form_bp
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from helpers.decorators import approved_required, staff_required
from models.meta_project import MetaProject
from models.sequencing_upload import SequencingUpload
import logging

logger = logging.getLogger("my_app_logger")


@upload_form_bp.route("/meta_projects", endpoint="meta_projects_list")
@login_required
@approved_required
@staff_required
def meta_projects_list():
    """Renders a list of all Meta Projects for staff and admins."""
    # Use the model class instead of raw DB queries in the view
    meta_projects = MetaProject.get_all()
    return render_template(
        "meta_projects_list.html", meta_projects=meta_projects
    )


@upload_form_bp.route("/meta_project/new", endpoint="new_meta_project")
@login_required
@approved_required
def new_meta_project():
    """Renders the form to create a new meta project."""
    return render_template("new_meta_project.html")


@upload_form_bp.route(
    "/meta_project/create", methods=["POST"], endpoint="create_meta_project"
)
@login_required
@approved_required
def create_meta_project_handler():
    """Handles the POST request to create a meta project and redirects to its management page."""
    name = request.form.get("name")
    if not name:
        flash("Project name is required.", "danger")
        return redirect(url_for("upload_form_bp.new_meta_project"))

    try:
        meta_id = MetaProject.create(name=name, user_id=current_user.id)
        flash(f"Meta Project '{name}' created successfully.", "success")
        return redirect(
            url_for(
                "upload_form_bp.meta_project_form", meta_project_id=meta_id
            )
        )
    except Exception as e:
        logger.error(f"Error creating meta project: {e}")
        flash("An error occurred during project creation.", "danger")
        return redirect(url_for("upload_form_bp.new_meta_project"))


@upload_form_bp.route("/meta_project/form", endpoint="meta_project_form")
@login_required
@approved_required
@staff_required
def meta_project_form():
    meta_id = request.args.get("meta_project_id")
    if not meta_id:
        return redirect(url_for("upload_form_bp.meta_projects_list"))

    meta_data = MetaProject.get(meta_id)
    available_uploads = SequencingUpload.get_all()

    # --- Sorting Logic Start ---
    # We sort by two criteria:
    # 1. Is it selected? (0 if yes, 1 if no -> putting yes at the top)
    # 2. Created date (descending -> newest projects first within their groups)
    selected_ids = set(meta_data.get("upload_ids", []))

    available_uploads.sort(
        key=lambda x: (
            0 if x.get("id") in selected_ids else 1,
            -(x.get("created_at").timestamp() if x.get("created_at") else 0),
            x.get("id"),  # Tertiary sort by ID to ensure a fixed order
        )
    )
    # --- Sorting Logic End ---

    lotus2_report = MetaProject.check_lotus2_reports_exist(meta_id)
    rscripts_report = MetaProject.check_rscripts_reports_exist(meta_id)
    mapping_files_exist = MetaProject.check_mapping_files_exist(meta_id)
    regions = MetaProject.get_regions(meta_id)
    return render_template(
        "meta_project_form.html",
        meta_id=meta_id,
        meta_data=meta_data,
        available_uploads=available_uploads,
        lotus2_report=lotus2_report,
        rscripts_report=rscripts_report,
        mapping_files_exist=mapping_files_exist,
        regions=regions,
        is_admin=current_user.admin,
    )


@upload_form_bp.route(
    "/meta_project/add_uploads",
    methods=["POST"],
    endpoint="meta_project_add_uploads",
)
@login_required
@approved_required
def meta_project_add_uploads():
    meta_id = request.form.get("meta_project_id")
    upload_ids = request.form.getlist("upload_ids[]")

    MetaProject.update_uploads(meta_id, upload_ids)
    return jsonify({"result": "ok"})


@upload_form_bp.route(
    "/meta_project/generate_mapping",
    methods=["POST"],
    endpoint="generate_meta_mapping",
)
@login_required
@approved_required
@staff_required
def generate_meta_mapping():
    """Handles the generation of combined mapping files for all projects in a meta project."""
    meta_id = request.form.get("meta_project_id")
    mode = request.form.get("mode", "all")

    if not meta_id:
        return (
            jsonify(
                {"result": "error", "message": "Meta Project ID is missing"}
            ),
            400,
        )

    try:
        # Call the coordination logic in the model
        MetaProject.generate_mapping_files(meta_id, mode)
        return jsonify(
            {
                "result": "1",
                "message": "Combined mapping files generated successfully",
            }
        )
    except Exception as e:
        logger.error(f"Error generating meta mapping for ID {meta_id}: {e}")
        return jsonify({"result": "error", "message": str(e)}), 500
