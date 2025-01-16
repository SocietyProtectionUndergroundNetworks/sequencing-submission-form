import logging
from flask import (
    redirect,
    Blueprint,
    render_template,
    request,
    url_for,
    jsonify,
)
from flask_login import current_user, login_required
from models.taxonomy import TaxonomyManager
from models.sequencing_sample import SequencingSample
from models.sequencing_upload import SequencingUpload

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

taxonomy_bp = Blueprint("taxonomy", __name__)


# Custom admin_required decorator
def admin_required(view_func):
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(
                url_for("user.login")
            )  # Adjust 'login' to your actual login route
        elif not current_user.admin:
            # Redirect non-admin users to some unauthorized page
            return redirect(url_for("user.only_admins"))
        return view_func(*args, **kwargs)

    return decorated_view


# Custom staff_required decorator
def staff_required(view_func):
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(
                url_for("user.login")
            )  # Adjust 'login' to your actual login route
        elif not (current_user.spun_staff or current_user.admin):
            # Redirect users who are neither staff nor admin
            return redirect(url_for("user.only_staff"))
        return view_func(*args, **kwargs)

    return decorated_view


# Custom approved_required decorator
def approved_required(view_func):
    def decorated_approved_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(
                url_for("user.login")
            )  # Adjust 'login' to your actual login route
        elif not current_user.approved:
            # Redirect non-approved users to some unauthorized page
            return redirect(url_for("user.only_approved"))
        return view_func(*args, **kwargs)

    return decorated_approved_view


@taxonomy_bp.route(
    "/taxonomy/search", methods=["GET"], endpoint="taxonomy_search"
)
@staff_required
@login_required
def taxonomy_search():

    return render_template("taxonomy.html")


@taxonomy_bp.route(
    "/taxonomy/search-results",
    methods=["GET"],
    endpoint="taxonomy_search_results",
)
@staff_required
@login_required
def taxonomy_search_results():
    # Extract search parameters
    domain = request.args.get("domain")
    phylum = request.args.get("phylum")
    class_ = request.args.get("class")
    order = request.args.get("order")
    family = request.args.get("family")
    genus = request.args.get("genus")
    species = request.args.get("species")

    # Use TaxonomyManager to perform the search
    all_results = TaxonomyManager.search(
        domain=domain,
        phylum=phylum,
        class_=class_,
        order=order,
        family=family,
        genus=genus,
        species=species,
    )

    total_results = len(all_results)  # Get total number of results
    limited_results = all_results[:500]  # Return only the first 500 results

    return jsonify({"data": limited_results, "total_results": total_results})


@taxonomy_bp.route(
    "/taxonomy/show_otus",
    methods=["GET"],
    endpoint="taxonomy_show_otus",
)
@login_required
@approved_required
def taxonomy_show_otus():
    sample_id = request.args.get("sample_id", "").strip()
    region = request.args.get("region", "").strip()

    # Validate region
    if region not in ["ITS1", "ITS2"]:
        return (
            render_template("error.html", message="Invalid region specified."),
            400,
        )

    # Query the OTUs for the sample and region
    otus = TaxonomyManager.get_otus(sample_id=sample_id, region=region)

    sample = SequencingSample.get(sample_id)
    upload = SequencingUpload.get(sample.sequencingUploadId)

    # Render the template with OTUs data
    return render_template(
        "otus.html",
        sample_id=sample_id,
        region=region,
        otus=otus,
        sample=sample,
        upload=upload,
    )
