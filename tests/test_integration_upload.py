import pytest
import os
from flask import url_for
from models.db_model import SequencingUploadsTable, SequencingSamplesTable
from flask_login import login_user
from tests.test_helpers import _create_dummy_user_and_bucket_dependencies
from helpers.dbm import session_scope


@pytest.mark.usefixtures("app", "db_session")
def test_upload_process_common_fields_creation(
    client, db_session, mocker, app
):
    # Step 1: Create dummy user and log them in
    test_user, test_project = _create_dummy_user_and_bucket_dependencies(
        db_session
    )

    with client.session_transaction() as sess:
        sess["_user_id"] = test_user

    # Step 2: Mock Slack sending to prevent real calls
    mocker.patch("helpers.slack.send_message_to_slack", return_value=None)

    # Step 3: Submit the form
    response = client.post(
        "/upload_process_common_fields",
        data={
            "project_id": test_project,
            "using_scripps": "no",
            "other_field": "some_value",
            "process_id": "",
            "region_1_forward_primer": "ITS3",
            "region_1_reverse_primer": "ITS4",
            "region_2_forward_primer": "WANDA",
            "region_2_reverse_primer": "AML2",
            "Sequencing_platform": "Illumina NextSeq",
        },
        follow_redirects=True,
    )

    # Step 4: Assert response is valid
    assert response.status_code == 200
    data = response.get_json()
    assert data["result"] == "ok"
    process_id = int(data["process_id"])
    print("The process id is: " + str(process_id))
    assert isinstance(process_id, int)

    # Step 5: Check upload was created in DB
    upload = db_session.get(SequencingUploadsTable, process_id)
    assert upload is not None
    assert upload.project_id == test_project

    # Step 6: Upload the metadata CSV file
    test_csv_path = os.path.join(
        os.path.dirname(__file__), "test_metadata.csv"
    )

    with open(test_csv_path, "rb") as f:
        data = {
            "file": (f, "test_metadata.csv"),
            "using_scripps": "no",
            "process_id": str(process_id),
        }
        response = client.post(
            "/upload_metadata_file",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["result"]["status"] == 1

    # Verify sample IDs were created and returned
    sample_records = json_data["data"]
    assert all(
        sample.get("id") is not None for sample in sample_records if sample
    )  # ensure sample ids exist

    # Check that these sample IDs are actually in the DB
    with session_scope() as fresh_session:
        for sample in sample_records:
            sample_id = sample.get("id")
            if sample_id is not None:

                db_sample = (
                    fresh_session.query(SequencingSamplesTable)
                    .filter_by(id=sample_id)
                    .first()
                )
                assert db_sample is not None

    # Step 7: Confirm the metadata upload
    response = client.post(
        "/sequencing_confirm_metadata",
        data={"process_id": process_id},
        follow_redirects=True,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["result"] == 1

    # Verify in the DB that the upload is marked confirmed
    with session_scope() as fresh_session:
        upload = fresh_session.get(SequencingUploadsTable, process_id)

        assert upload is not None
        assert upload.metadata_upload_confirmed is True
