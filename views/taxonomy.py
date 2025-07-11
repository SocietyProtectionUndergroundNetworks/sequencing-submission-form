import logging
import csv
import io
from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    Response,
)
from flask_login import login_required
from models.taxonomy import TaxonomyManager
from models.sequencing_sample import SequencingSample
from models.sequencing_upload import SequencingUpload
from models.sequencing_analysis_type import SequencingAnalysisType
from helpers.decorators import staff_required, approved_required

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

taxonomy_bp = Blueprint("taxonomy", __name__)


@taxonomy_bp.route(
    "/taxonomy/search", methods=["GET"], endpoint="taxonomy_search"
)
@staff_required
@login_required
def taxonomy_search():

    analysis_types = SequencingAnalysisType.get_all()
    return render_template("taxonomy.html", analysis_types=analysis_types)


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
    project = request.args.get("project")
    amf_filter = request.args.get("amf_filter")
    analysis_type = request.args.get("analysis_type")

    # The default should be with the filtering
    amf_filter_yes = True
    if amf_filter == "no":
        amf_filter_yes = False

    ecm_filter = request.args.get("ecm_filter")
    # The default should be with the filtering
    ecm_filter_yes = True
    if ecm_filter == "no":
        ecm_filter_yes = False

    # Use TaxonomyManager to perform the search
    all_results = TaxonomyManager.search(
        domain=domain,
        phylum=phylum,
        class_=class_,
        order=order,
        family=family,
        genus=genus,
        species=species,
        project=project,
        amf_filter=amf_filter_yes,
        ecm_filter=ecm_filter_yes,
        analysis_type=analysis_type,
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
    analysis_type_id = request.args.get("analysis_type_id", "").strip()
    amf_filter = request.args.get("amf_filter", 1)
    amf_filter = int(amf_filter) if amf_filter else 0

    ecm_filter = request.args.get("ecm_filter", 1)
    ecm_filter = int(ecm_filter) if ecm_filter else 0

    # Query the OTUs for the sample and region
    otus = TaxonomyManager.get_otus(
        sample_id=sample_id,
        region=region,
        analysis_type_id=analysis_type_id,
        amf_filter=amf_filter,
        ecm_filter=ecm_filter,
    )

    sample = SequencingSample.get(sample_id)
    upload = SequencingUpload.get(sample.sequencingUploadId)
    sample_analysis_types = SequencingSample.get_analysis_types_with_otus(
        sample_id
    )

    analysis_type = ""
    # Check if the analysis_type_id is a valid integer
    if analysis_type_id and analysis_type_id.isdigit():
        analysis_type_id = int(analysis_type_id)
        from models.sequencing_analysis_type import SequencingAnalysisType

        analysis = SequencingAnalysisType.get(analysis_type_id)
        analysis_type = analysis.name

    # Render the template with OTUs data
    return render_template(
        "otus.html",
        sample_id=sample_id,
        region=region,
        otus=otus,
        sample=sample,
        upload=upload,
        analysis_type=analysis_type,
        analysis_type_id=analysis_type_id,
        sample_analysis_types=sample_analysis_types,
        amf_filter=amf_filter,
        ecm_filter=ecm_filter,
    )


@taxonomy_bp.route(
    "/taxonomy/download_otus_csv",
    methods=["GET"],
    endpoint="taxonomy_download_otus_csv",
)
@login_required
@approved_required
def taxonomy_download_otus_csv():
    sample_id = request.args.get("sample_id", "").strip()
    region = request.args.get("region", "").strip()
    analysis_type_id = request.args.get("analysis_type_id", "").strip()
    sample = SequencingSample.get(sample_id)
    upload = SequencingUpload.get(sample.sequencingUploadId)
    amf_filter = request.args.get("amf_filter", 1)
    amf_filter = int(amf_filter) if amf_filter else 0

    ecm_filter = request.args.get("ecm_filter", 1)
    ecm_filter = int(ecm_filter) if ecm_filter else 0

    # Query the OTUs for the sample and region
    otus = TaxonomyManager.get_otus(
        sample_id=sample_id,
        region=region,
        analysis_type_id=analysis_type_id,
        amf_filter=amf_filter,
        ecm_filter=ecm_filter,
    )

    # Create an in-memory string buffer
    output = io.StringIO()
    csv_writer = csv.writer(
        output, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
    )

    # Write the header (adjust according to your OTU data structure)
    csv_writer.writerow(
        [
            "Project",
            "Sample_id",
            "Analysis_Type",
            "Domain",
            "Phylum",
            "Class",
            "Order",
            "Family",
            "Genus",
            "Species",
            "ReadsCount",
        ]
    )
    last_analysis_type = ""
    # Write the rows based on OTU data
    for otu in otus:
        last_analysis_type = otu["analysis_type"]
        csv_writer.writerow(
            [
                upload["project_id"],
                sample.SampleID,
                otu["analysis_type"],
                otu["domain"],
                otu["phylum"],
                otu["class"],
                otu["order"],
                otu["family"],
                otu["genus"],
                otu["species"],
                otu["abundance"],
            ]
        )

    # Seek to the start of the StringIO buffer
    # so it can be read from the beginning
    output.seek(0)
    filename = f"attachment;filename=otus_sample_{sample_id}"

    if region:
        filename += f"_region_{region}"

    if analysis_type_id:
        filename += f"_analysis_type_{last_analysis_type}"
    # Return the CSV as a response with appropriate headers for downloading
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"{filename}.csv"},
    )
