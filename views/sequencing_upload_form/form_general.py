from . import upload_form_bp
import os
import logging
from flask_login import login_required, current_user
from flask import (
    redirect,
    request,
    url_for,
    jsonify,
    render_template,
)
from helpers.decorators import (
    approved_required,
    admin_or_owner_required,
)
from sqlalchemy.inspection import inspect
from helpers.metadata_check import (
    get_columns_data,
    get_project_common_data,
    sanitize_data,
    get_primer_sets_regions,
    primers_forward_to_reverse,
)
from models.sequencing_upload import SequencingUpload
from models.bucket import Bucket
from helpers.fastqc import check_multiqc_report

logger = logging.getLogger("my_app_logger")


@upload_form_bp.route("/metadata_form", endpoint="metadata_form")
@login_required
@approved_required
@admin_or_owner_required
def metadata_form():
    my_buckets = {}
    map_key = os.environ.get("GOOGLE_MAP_API_KEY")
    google_sheets_template_url = os.environ.get("GOOGLE_SPREADSHEET_TEMPLATE")
    for my_bucket in current_user.buckets:
        my_buckets[my_bucket] = Bucket.get(my_bucket)
    expected_columns = get_columns_data(exclude=False)
    project_common_data = get_project_common_data()
    process_data = None
    process_id = request.args.get("process_id", "")
    primer_set_regions = get_primer_sets_regions()
    forward_primers = list(
        {key.split("/")[0]: None for key in primer_set_regions}.keys()
    )
    forward_to_reverse = primers_forward_to_reverse(primer_set_regions)
    samples_data = []
    sequencer_ids = []
    regions = SequencingUpload.get_regions()
    nr_files_per_sequence = 1
    valid_samples = False
    missing_sequencing_ids = []
    samples_data_complete = []
    extra_data = {}
    extra_data_keys = set()
    multiqc_report_exists = False
    mapping_files_exist = False
    has_empty_fastqc_report = False
    lotus2_report = []
    rscripts_report = []
    pdf_report = False
    is_owner = False
    total_uploaded_files = 0

    if process_id:
        process_data = SequencingUpload.get(process_id)
        if process_data is not None:
            is_owner = current_user.id == process_data["user_id"]

            nr_files_per_sequence = process_data["nr_files_per_sequence"]
            regions = process_data["regions"]

            samples_data = SequencingUpload.get_samples(process_id)

            samples_data = sanitize_data(samples_data)

            # lets create the extra data dictionary
            # Iterate through each sample in samples_data
            for sample in samples_data:
                # Ensure that both 'SampleID' and 'extracolumns_json'
                # exist in the sample
                if "SampleID" in sample:
                    extracolumns_json = sample.get("extracolumns_json")

                    if (
                        extracolumns_json
                    ):  # Check if extracolumns_json is not None
                        # Add to extra_data dictionary
                        extra_data[sample["SampleID"]] = extracolumns_json

                        # Update the set of unique keys with keys from the
                        # extracolumns_json dictionary
                        extra_data_keys.update(extracolumns_json.keys())
            # lets delete the extracolumns_json from the samples_data
            for sample in samples_data:
                if "extracolumns_json" in sample:
                    del sample["extracolumns_json"]
            sequencer_ids = SequencingUpload.get_sequencer_ids(process_id)
            valid_samples = SequencingUpload.validate_samples(process_id)
            missing_sequencing_ids = (
                SequencingUpload.check_missing_sequencer_ids(process_id)
            )
            samples_data_complete = (
                SequencingUpload.get_samples_with_sequencers_and_files(
                    process_id
                )
            )

            # check if we have files without fastq report
            has_empty_fastqc_report = any(
                not file.get("fastqc_report")
                for entry in samples_data_complete
                for sequencer in entry.get("sequencer_ids", [])
                for file in sequencer.get("uploaded_files", [])
            )

            total_uploaded_files = sum(
                len(sequencer["uploaded_files"])
                for sample in samples_data_complete
                for sequencer in sample.get("sequencer_ids", [])
            )

            multiqc_report_exists = check_multiqc_report(process_id)
            mapping_files_exist = SequencingUpload.check_mapping_files_exist(
                process_id
            )

            lotus2_report = SequencingUpload.check_lotus2_reports_exist(
                process_id
            )
            rscripts_report = SequencingUpload.check_rscripts_reports_exist(
                process_id
            )
            # check if pdf report exists
            r_scripts_report = os.path.join(
                "seq_processed",
                process_data["uploads_folder"],
                "r_output",
                "report.pdf",
            )
            if os.path.isfile(r_scripts_report):
                pdf_report = True
        else:
            return redirect(url_for("upload_form_bp.metadata_form"))

    return render_template(
        "metadata_form.html",
        my_buckets=my_buckets,
        map_key=map_key,
        expected_columns=expected_columns,
        project_common_data=project_common_data,
        process_data=process_data,
        process_id=process_id,
        samples_data=samples_data,
        regions=regions,
        sequencer_ids=sequencer_ids,
        forward_primers=forward_primers,
        forward_to_reverse=forward_to_reverse,
        nr_files_per_sequence=nr_files_per_sequence,
        google_sheets_template_url=google_sheets_template_url,
        valid_samples=valid_samples,
        missing_sequencing_ids=missing_sequencing_ids,
        samples_data_complete=samples_data_complete,
        is_admin=current_user.admin,
        multiqc_report_exists=multiqc_report_exists,
        extra_data_keys=extra_data_keys,
        extra_data=extra_data,
        mapping_files_exist=mapping_files_exist,
        lotus2_report=lotus2_report,
        has_empty_fastqc_report=has_empty_fastqc_report,
        rscripts_report=rscripts_report,
        pdf_report=pdf_report,
        is_owner=is_owner,
        total_uploaded_files=total_uploaded_files,
    )


@upload_form_bp.route(
    "/upload_process_common_fields",
    methods=["POST"],
    endpoint="upload_process_common_fields",
)
@login_required
@approved_required
def upload_process_common_fields():
    from helpers.slack import send_message_to_slack

    # Parse form data from the request
    form_data = request.form.to_dict()
    if form_data["process_id"]:
        process_id = form_data["process_id"]
        if current_user.admin:
            from models.db_model import SequencingUploadsTable

            # Get the valid columns of the SequencingUploadsTable
            valid_fields = {
                column.key
                for column in inspect(SequencingUploadsTable).columns
            }
            # Loop through form_data keys and update fields that are valid
            for key, value in form_data.items():
                logger.info(
                    "The key is " + str(key) + " and the value " + str(value)
                )
                if key in valid_fields and key not in [
                    "using_scripps",
                    "project_id",
                ]:
                    SequencingUpload.update_field(
                        id=process_id, fieldname=key, value=value
                    )

    else:
        process_id = SequencingUpload.create(datadict=form_data)
        send_message_to_slack(
            "STARTING: A v2 upload was initiated by filling "
            + "in project common data by the user "
            + current_user.name
            + ". The project is: "
            + str(form_data["project_id"])
            + ". The id of the upload is: "
            + str(process_id)
        )

    # Return the result as JSON
    return (
        jsonify({"result": "ok", "process_id": process_id}),
        200,
    )
