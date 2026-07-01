import io
import pytest
from unittest.mock import patch

from models.db_model import (
    MobileAppProjectTable,
    MobileAppStagingSampleTable,
    MobileAppStagingPhotoTable,
)

API_KEY = "test-mobile-api-key"
_AUTH = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("MOBILE_API_KEY", API_KEY)


@pytest.fixture(autouse=True)
def _silence_slack():
    with patch("views.mobile_api.send_message_to_slack_mobile"):
        yield


# ---------------------------------------------------------------------------
# Test 1: batch sample submission auto-creates a missing project and stores
#         the integer FK (not the UUID string) on the sample row.
# ---------------------------------------------------------------------------
def test_batch_samples_auto_creates_project_with_integer_fk(
    client, db_session
):
    project_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    payload = {
        "samples": [
            {
                "sample_id": "AUTO001",
                "project_id": project_uuid,
                "project_name": "Auto-created Project",
                "submitter_id": "field@example.com",
                "date_collected": "2026-07-01",
                "latitude": 51.5,
                "longitude": -0.1,
            }
        ]
    }

    response = client.post("/api/samples/batch", json=payload, headers=_AUTH)
    assert response.status_code == 200
    assert response.get_json()["inserted"] == 1

    # Project must have been created automatically
    db_session.expire_all()
    project = (
        db_session.query(MobileAppProjectTable)
        .filter_by(project_id=project_uuid)
        .first()
    )
    assert project is not None, "project was not auto-created"
    assert project.name == "Auto-created Project"

    # Sample must reference the project's integer PK, not the UUID string
    sample = (
        db_session.query(MobileAppStagingSampleTable)
        .filter_by(sample_id="AUTO001")
        .first()
    )
    assert sample is not None
    assert sample.project_id == project.id


# ---------------------------------------------------------------------------
# Test 2: uploading the same photo bytes twice for the same sample must
#         result in exactly one record in mobile_app_staging_photos.
# ---------------------------------------------------------------------------
def test_upload_photo_deduplication(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("MOBILE_PHOTOS_DIR", str(tmp_path))

    project_uuid = "11111111-2222-3333-4444-555555555555"
    project = MobileAppProjectTable(
        project_id=project_uuid,
        name="Dedup Test Project",
        submitter_id="field@example.com",
    )
    db_session.add(project)
    db_session.commit()

    photo_bytes = (
        b"\xff\xd8\xff\xe0" + b"fake-jpeg-payload"
    )  # minimal JPEG-like header

    def _post_photo():
        return client.post(
            "/api/photos",
            data={
                "sample_id": "DEDUP001",
                "project_id": project_uuid,
                "submitter_id": "field@example.com",
                "photo": (io.BytesIO(photo_bytes), "site.jpg", "image/jpeg"),
            },
            headers=_AUTH,
            content_type="multipart/form-data",
        )

    r1 = _post_photo()
    assert r1.status_code == 200

    r2 = _post_photo()
    assert (
        r2.status_code == 200
    )  # duplicate is accepted silently, not rejected

    db_session.expire_all()
    count = (
        db_session.query(MobileAppStagingPhotoTable)
        .filter_by(sample_id="DEDUP001")
        .count()
    )
    assert count == 1, f"expected 1 photo record, got {count}"


# ---------------------------------------------------------------------------
# Test 3: a fully-populated sample payload (every field the mobile app sends)
#         is accepted and stored correctly — guards against model/API drift.
# ---------------------------------------------------------------------------
def test_batch_samples_full_payload_accepted(client, db_session):
    project_uuid = "cccccccc-dddd-eeee-ffff-000000000000"

    full_sample = {
        "sample_id": "FULL001",
        "project_id": project_uuid,
        "project_name": "Full Payload Project",
        "submitter_id": "collector@example.com",
        "date_collected": "2026-06-30",
        "latitude": 44.7891751,
        "longitude": 6.4596684,
        "accuracy": 4.5,
        "elevation": 1481.68,
        "sample_type": "soil",
        "sample_or_control": "True sample",
        "transport": "dry ice",
        "drying": "silica gel",
        "soil_depth": "0-20cm",
        "grid_size": "30m",
        "land_use": "forest",
        "agricultural": "No",
        "vegetation": "Mixed montane scrub with pines and wild lavender",
        "notes": "Rocky terrain, high species richness",
        "dna_concentration_ng_ul": "3.91",
    }

    response = client.post(
        "/api/samples/batch",
        json={"samples": [full_sample]},
        headers=_AUTH,
    )
    assert response.status_code == 200
    assert response.get_json()["inserted"] == 1

    db_session.expire_all()
    row = (
        db_session.query(MobileAppStagingSampleTable)
        .filter_by(sample_id="FULL001")
        .first()
    )
    assert row is not None

    from datetime import date

    assert row.submitter_id == "collector@example.com"
    assert row.project_name == "Full Payload Project"
    assert row.date_collected == date(2026, 6, 30)
    assert float(row.latitude) == pytest.approx(44.7891751, rel=1e-5)
    assert float(row.longitude) == pytest.approx(6.4596684, rel=1e-5)
    assert float(row.accuracy) == pytest.approx(4.5, rel=1e-3)
    assert float(row.elevation) == pytest.approx(1481.68, rel=1e-3)
    assert row.sample_type == "soil"
    assert row.sample_or_control == "True sample"
    assert row.transport == "dry ice"
    assert row.drying == "silica gel"
    assert row.soil_depth == "0-20cm"
    assert row.grid_size == "30m"
    assert row.land_use == "forest"
    assert row.agricultural == "No"
    assert row.vegetation == "Mixed montane scrub with pines and wild lavender"
    assert row.notes == "Rocky terrain, high species richness"
    assert row.dna_concentration_ng_ul == "3.91"
