import uuid
from models.db_model import (
    UserTable,
    BucketTable,
    ResolveEcoregionsTable,
    Domain,
    Phylum,
    Class,
    Order,
    Family,
    Genus,
    Species,
    Taxonomy,
    SequencingSamplesTable,
)
from unittest.mock import MagicMock
from models.sequencing_upload import SequencingUpload
from models.sequencing_sample import SequencingSample


def _create_dummy_user_and_bucket_dependencies(db_session):
    """
    Creates and commits a dummy user and a dummy
    bucket to satisfy foreign key constraints.
    Returns the generated user_id and project_id.
    """
    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())

    dummy_user = UserTable(
        id=user_id,
        name=f"Test User {user_id[:8]}",
        email=f"test.user.{user_id[:8]}@example.com",
        profile_pic=f"http://example.com/pic/{user_id[:8]}.jpg",
        admin=False,
        approved=True,
    )
    dummy_bucket = BucketTable(id=project_id)

    db_session.add(dummy_user)
    db_session.add(dummy_bucket)
    db_session.commit()  # Commit immediately so they are available for checks

    return user_id, project_id


def _create_dummy_sequencing_upload(db_session, mocker, app_fixture, **kwargs):
    """
    Helper function to create a SequencingUploadsTable
    entry with its dependencies.
    Handles user and bucket creation, Flask context, and current_user mocking.
    Returns the ID of the created SequencingUpload, and the user/project IDs.
    """
    # Create user and bucket dependencies for this specific upload
    user_id, project_id = _create_dummy_user_and_bucket_dependencies(
        db_session
    )

    # Mock current_user within an app.test_request_context
    mock_current_user = MagicMock(
        id=user_id,
        is_authenticated=True,
        is_active=True,
        is_anonymous=False,
        get_id=lambda: user_id,
    )
    # Patch current_user where it's used in the create method
    mocker.patch("flask_login.current_user", mock_current_user)
    mocker.patch("models.sequencing_upload.current_user", mock_current_user)
    mocker.patch(
        "pathlib.Path.mkdir"
    )  # Mock Path.mkdir to prevent actual directory creation

    # Default data for a sequencing upload
    # Note: user_id is NOT included here as
    # SequencingUpload.create pulls it from current_user.id
    default_upload_data = {
        "project_id": project_id,  # Link to the created project_id
        "latest_metadata_filename": "generated_metadata.csv",
        "sequencing_upload_filedata": {"auto_gen": True},
        "using_scripps": "no",
        "Country": "Testland",
        "Sequencing_platform": "Illumina NovaSeq",
        "Sequencing_facility": "Test Facility",
        "Expedition_lead": "Automated Test",
        "Collaborators": "Internal",
        "region_1_forward_primer": "ITS3",
        "region_1_reverse_primer": "ITS4",
        "region_2_forward_primer": "0",
        "region_2_reverse_primer": "0",
        "Extraction_method": "AutoMethod",
        "Multiple_sequencing_runs": "No",
        "DNA_conc_instrument": "MockInstrument",
        "files_uploading_confirmed": True,
        "share_url": None,
        "share_sync_completed": False,
    }

    # Override defaults with any provided kwargs
    upload_data = {**default_upload_data, **kwargs}

    # Call SequencingUpload.create within the app context
    with app_fixture.test_request_context():
        sequencing_upload_id = SequencingUpload.create(upload_data)
    db_session.commit()  # Ensure the upload is committed

    return (
        sequencing_upload_id,
        user_id,
        project_id,
        upload_data,
    )  # Return relevant info


def _create_dummy_sampling_record(db_session, mocker, app_fixture, **kwargs):
    """
    Creates and commits a SequencingSamplesTable row via SequencingSample.create.
    Returns (sample_id, sequencing_upload_id, sample_data, sample_row).
    """
    sequencing_upload_id, user_id, project_id, upload_data = (
        _create_dummy_sequencing_upload(db_session, mocker, app_fixture)
    )
    unique = uuid.uuid4().hex[:8]
    default_sample_data = {
        "SampleID": f"TEST-SAMPLE-{unique}",
    }

    sample_data = {**default_sample_data, **kwargs}

    with app_fixture.test_request_context():
        sample_id = SequencingSample.create(sequencing_upload_id, sample_data)

    db_session.commit()

    sample_row = (
        db_session.query(SequencingSamplesTable).filter_by(id=sample_id).one()
    )
    return sample_id, sequencing_upload_id, sample_data, sample_row


def _create_dummy_ecoregion(db_session, ecoregion_id, name, fid, objectid):
    """
    Creates and commits a dummy ResolveEcoregionsTable entry.
    Ensures FID and OBJECTID are provided and match the non-nullable columns.
    Returns the created ecoregion object.
    """

    ecoregion = ResolveEcoregionsTable(
        id=ecoregion_id,
        FID=fid,
        OBJECTID=objectid,
        ecoregion_name=name,
        # Providing default values for other nullable fields for completeness
        biome_number=1,
        biome_name="Mock Biome",
        realm_name="Mock Realm",
        nature_needs_half_number=1,
        ecoregion_unique_id=12345,
        shape_leng=1.0,
        nature_needs_half_description="Mock Description",
        color="#FFFFFF",
        biome_color="#CCCCCC",
        nature_needs_half_color="#EEEEEE",
        license="MIT",
        shape_area=10.0,
        shape_length=2.0,
    )
    db_session.add(ecoregion)
    db_session.commit()
    return ecoregion


def _create_dummy_taxonomy_hierarchy(
    db_session,
    domain_name="Fungi",
    phylum_name="Ascomycota",
    class_name="Saccharomycetes",
    order_name="Saccharomycetales",
    family_name="Saccharomycetaceae",
    genus_name="Saccharomyces",
    species_name="cerevisiae",
    taxonomy_id=None,  # Optional, to set a specific ID for Taxonomy table
):
    """
    Creates a full dummy taxonomy hierarchy
    (Domain to Species) and a corresponding
    Taxonomy table entry. Returns the Taxonomy object.
    """
    domain = db_session.query(Domain).filter_by(name=domain_name).first()
    if not domain:
        domain = Domain(name=domain_name)
        db_session.add(domain)
        db_session.commit()
        db_session.refresh(domain)

    phylum = (
        db_session.query(Phylum)
        .filter_by(name=phylum_name, domain_id=domain.id)
        .first()
    )
    if not phylum:
        phylum = Phylum(name=phylum_name, domain=domain)
        db_session.add(phylum)
        db_session.commit()
        db_session.refresh(phylum)

    class_ = (
        db_session.query(Class)
        .filter_by(name=class_name, phylum_id=phylum.id)
        .first()
    )
    if not class_:
        class_ = Class(name=class_name, phylum=phylum)
        db_session.add(class_)
        db_session.commit()
        db_session.refresh(class_)

    order = (
        db_session.query(Order)
        .filter_by(name=order_name, class_id=class_.id)
        .first()
    )
    if not order:
        order = Order(name=order_name, class_=class_)
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

    family = (
        db_session.query(Family)
        .filter_by(name=family_name, order_id=order.id)
        .first()
    )
    if not family:
        family = Family(name=family_name, order=order)
        db_session.add(family)
        db_session.commit()
        db_session.refresh(family)

    genus = (
        db_session.query(Genus)
        .filter_by(name=genus_name, family_id=family.id)
        .first()
    )
    if not genus:
        genus = Genus(name=genus_name, family=family)
        db_session.add(genus)
        db_session.commit()
        db_session.refresh(genus)

    species = (
        db_session.query(Species)
        .filter_by(name=species_name, genus_id=genus.id)
        .first()
    )
    if not species:
        species = Species(name=species_name, genus=genus)
        db_session.add(species)
        db_session.commit()
        db_session.refresh(species)

    # Create the Taxonomy entry linking all levels
    taxonomy_entry = Taxonomy(
        id=taxonomy_id,  # Use provided ID or let it autoincrement
        domain_id=domain.id,
        phylum_id=phylum.id,
        class_id=class_.id,
        order_id=order.id,
        family_id=family.id,
        genus_id=genus.id,
        species_id=species.id,
    )
    db_session.add(taxonomy_entry)
    db_session.commit()
    db_session.refresh(taxonomy_entry)

    return taxonomy_entry
