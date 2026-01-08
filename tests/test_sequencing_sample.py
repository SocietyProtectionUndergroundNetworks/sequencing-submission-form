import pytest
from tests.test_helpers import _create_dummy_sampling_record

def test_sample_normal_value_saved(db_session, mocker, app):
    _, _, _, row = _create_dummy_sampling_record(
        db_session,
        mocker,
        app,
        Agricultural_land="No",
    )
    assert row.Agricultural_land == "No"

def test_sample_invalid_value_rejected(db_session, mocker, app):
    with pytest.raises(ValueError):
        _create_dummy_sampling_record(
            db_session,
            mocker,
            app,
            Agricultural_land="nooo",
        )

def test_sample_wrong_case_is_normalised_in_db(db_session, mocker, app):
    _, _, _, row = _create_dummy_sampling_record(
        db_session,
        mocker,
        app,
        Agricultural_land="no",
    )
    assert row.Agricultural_land == "No"