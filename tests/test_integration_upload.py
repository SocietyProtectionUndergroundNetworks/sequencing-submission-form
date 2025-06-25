import pytest
import io
import os
import hashlib
import json
from models.db_model import (
    SequencingFilesUploadedTable,
    SequencingSequencerIDsTable,
    SequencingSamplesTable,
    SequencingUploadsTable,
)
from models.sequencing_upload import SequencingUpload
from tests.test_helpers import _create_dummy_user_and_bucket_dependencies
from helpers.dbm import session_scope


def calculate_md5_bytes(file_bytes):
    md5_hash = hashlib.md5()
    md5_hash.update(file_bytes)
    return md5_hash.hexdigest()


def assert_uploaded_files(process_id, expected_filenames):
    with session_scope() as session:
        results = (
            session.query(
                SequencingFilesUploadedTable.original_filename,
                SequencingFilesUploadedTable.new_name,
                SequencingFilesUploadedTable.total_sequences_number,
            )
            .join(
                SequencingSequencerIDsTable,
                SequencingFilesUploadedTable.sequencerId
                == SequencingSequencerIDsTable.id,
            )
            .join(
                SequencingSamplesTable,
                SequencingSequencerIDsTable.sequencingSampleId
                == SequencingSamplesTable.id,
            )
            .filter(SequencingSamplesTable.sequencingUploadId == process_id)
            .all()
        )

        # Create a lookup by original_filename
        found_files = {row.original_filename: row for row in results}

        for filename in expected_filenames:
            assert (
                filename in found_files
            ), f"{filename} not found in uploaded files"
            row = found_files[filename]
            assert (
                row.total_sequences_number == 10000
            ), f"{filename} has incorrect sequence count: {row.total_sequences_number}"
            assert row.new_name is not None and row.new_name.endswith(
                ".fastq.gz"
            ), f"{filename} has invalid new_name: {row.new_name}"


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

    # Step 8: Upload the sequencer IDs CSV
    sequencer_ids_csv_path = os.path.join("tests", "test_sequencer_ids.csv")
    with open(sequencer_ids_csv_path, "rb") as f:
        response = client.post(
            "/upload_sequencer_ids_file",
            data={
                "file": (f, "test_sequencer_ids.csv"),
                "process_id": process_id,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    assert response.status_code == 200
    data = response.get_json()
    assert "missing_sequencing_ids" in data  # This is always returned
    # Optionally assert there are none missing:
    assert data["missing_sequencing_ids"] == []

    with session_scope() as session:
        # Get all samples associated with the process_id (i.e., sequencingUploadId)
        samples = (
            session.query(SequencingSamplesTable)
            .filter(SequencingSamplesTable.sequencingUploadId == process_id)
            .all()
        )

        for sample in samples:
            sequencer_id_records = (
                session.query(SequencingSequencerIDsTable)
                .filter(
                    SequencingSequencerIDsTable.sequencingSampleId == sample.id
                )
                .all()
            )

            # Check there are exactly 2 records
            assert (
                len(sequencer_id_records) == 2
            ), f"Expected 2 records for sample ID {sample.id}, found {len(sequencer_id_records)}"

            # Check that one is for ITS2 and one is for SSU
            regions = {rec.Region for rec in sequencer_id_records}
            assert regions == {
                "ITS2",
                "SSU",
            }, f"Unexpected regions for sample ID {sample.id}: {regions}"

    # Step 9: Upload the fastq files
    file_paths = [
        "tests/fastq_files/sample1_ITS2_R1.fastq.gz",
        "tests/fastq_files/sample1_ITS2_R2.fastq.gz",
        "tests/fastq_files/sample2_ITS2_R1.fastq.gz",
        "tests/fastq_files/sample2_ITS2_R2.fastq.gz",
        "tests/fastq_files/sample1_SSU_R1.fastq.gz",
        "tests/fastq_files/sample1_SSU_R2.fastq.gz",
        "tests/fastq_files/sample2_SSU_R1.fastq.gz",
        "tests/fastq_files/sample2_SSU_R2.fastq.gz",
    ]

    chunk_size = 10 * 1024 * 1024  # 10MB chunks like your JS

    for file_path in file_paths:
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        # Step 1: Check filename matching
        resp = client.post(
            "/check_filename_matching",
            data={"process_id": process_id, "filename": filename},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["result"] == 1
        sequencer_ids = data.get("matching_sequencer_id")
        assert sequencer_ids, f"No sequencer ID matched for {filename}"

        # Step 2: Calculate MD5 for whole file
        md5 = calculate_md5_bytes(file_bytes)

        # Step 3: Split into chunks
        chunks = [
            file_bytes[i : i + chunk_size]
            for i in range(0, len(file_bytes), chunk_size)
        ]

        # Step 4: Upload each chunk
        for idx, chunk in enumerate(chunks, start=1):
            # Using query params like your JS sends in r.opts.query
            query_params = {
                "process_id": process_id,
                "filename": filename,
                "resumableChunkNumber": idx,
                "resumableTotalChunks": len(chunks),
            }
            # Send chunk as multipart form file under 'file'
            data = {"file": (io.BytesIO(chunk), filename)}
            # Compose URL with query parameters
            url = "/sequencing_upload_chunk?" + "&".join(
                f"{k}={v}" for k, v in query_params.items()
            )
            chunk_resp = client.post(
                url,
                data=data,
                content_type="multipart/form-data",
            )
            assert chunk_resp.status_code == 200

        # Step 5: Finalize upload
        fileopts = {
            "process_id": process_id,
            "filename": filename,
            "filesize": len(file_bytes),
            "filechunks": len(chunks),
            "fileindex": filename,
            "sequencerId": sequencer_ids,
            "md5": md5,
        }

        finalize_resp = client.post(
            "/sequencing_file_upload_completed",
            data={
                "process_id": process_id,
                "filename": filename,
                "fileopts": json.dumps(fileopts),
            },
        )
        assert finalize_resp.status_code == 200
        finalize_data = finalize_resp.get_json()
        print(finalize_data)
        assert finalize_data["result"] == 1

    # Step 10: Force the application to calculate the total_sequences_number
    SequencingUpload.get_samples_with_sequencers_and_files(process_id)

    # Step 11: Assert each file is uploaded correctly in the DB
    assert_uploaded_files(
        process_id, [os.path.basename(p) for p in file_paths]
    )

    # Step 12: Trigger the counting of the adapters
    SequencingUpload.adapters_count(process_id)

    # Step 13: Assert adapter counts match expected
    expected_adapters = {
        "sample1_ITS2_R": {
            "fwd_read_fwd_adap": 9751,
            "rev_read_rev_adap": 9933,
            "fwd_rev_adap": 9691,
            "fwd_rev_mrg_adap": 9052,
        },
        "sample1_SSU_R": {
            "fwd_read_fwd_adap": 6626,
            "rev_read_rev_adap": 9675,
            "fwd_rev_adap": 6474,
            "fwd_rev_mrg_adap": 4825,
        },
        "sample2_SSU_R": {
            "fwd_read_fwd_adap": 8662,
            "rev_read_rev_adap": 9827,
            "fwd_rev_adap": 8533,
            "fwd_rev_mrg_adap": 7759,
        },
        "sample2_ITS2_R": {
            "fwd_read_fwd_adap": 9117,
            "rev_read_rev_adap": 9940,
            "fwd_rev_adap": 9068,
            "fwd_rev_mrg_adap": 8367,
        },
    }

    with session_scope() as session:
        results = (
            session.query(
                SequencingSequencerIDsTable.SequencerID,
                SequencingSequencerIDsTable.fwd_read_fwd_adap,
                SequencingSequencerIDsTable.rev_read_rev_adap,
                SequencingSequencerIDsTable.fwd_rev_adap,
                SequencingSequencerIDsTable.fwd_rev_mrg_adap,
            )
            .join(
                SequencingSamplesTable,
                SequencingSequencerIDsTable.sequencingSampleId
                == SequencingSamplesTable.id,
            )
            .filter(SequencingSamplesTable.sequencingUploadId == process_id)
            .all()
        )

        for row in results:
            seq_id = row.SequencerID
            assert seq_id in expected_adapters, f"{seq_id} not expected"
            expected = expected_adapters[seq_id]
            for key, expected_value in expected.items():
                actual_value = getattr(row, key)
                assert actual_value == expected_value, (
                    f"{seq_id} {key} mismatch: "
                    f"expected {expected_value}, got {actual_value}"
                )
