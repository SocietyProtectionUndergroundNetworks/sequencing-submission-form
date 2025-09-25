from datetime import datetime
from tests.test_helpers import (
    _create_dummy_user_and_bucket_dependencies,
    _create_dummy_ecoregion,
    _create_dummy_sequencing_upload,
    _create_dummy_taxonomy_hierarchy,
)

# Assuming models.db_model.py contains Base and SequencingUploadsTable
from models.db_model import (
    SequencingUploadsTable,
    SequencingAnalysisTypesTable,
    SequencingSamplesTable,
    SequencingAnalysisTable,
    OTU,
)
from models.sequencing_upload import SequencingUpload


# The test function for SequencingUpload.create
def test_create_sequencing_upload(db_session, mocker, app):
    """
    Tests the creation of a SequencingUpload record using the helper function.
    """
    # Create dummy user and bucket for the first scenario
    sequencing_upload_id, test_user_id_1, test_project_id_1, test_data = (
        _create_dummy_sequencing_upload(
            db_session, mocker, app, using_scripps="no"
        )
    )

    assert isinstance(sequencing_upload_id, int)
    assert sequencing_upload_id > 0
    # Path.mkdir is mocked inside the helper,
    # so no need to assert directly here unless needed for specific test
    # Path.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    # This would need more complex mocking if called multiple times

    created_record = (
        db_session.query(SequencingUploadsTable)
        .filter_by(id=sequencing_upload_id)
        .first()
    )
    assert created_record is not None
    assert created_record.user_id == test_user_id_1
    assert created_record.project_id == test_data["project_id"]
    assert created_record.using_scripps is False
    assert created_record.region_1 == SequencingUpload.get_region(
        "ITS3", "ITS4"
    )  # Default primers in helper
    assert created_record.Sequencing_regions_number == 1
    assert created_record.uploads_folder is not None
    assert f"{sequencing_upload_id:05}" in created_record.uploads_folder

    # Test 'using_scripps' = 'yes' path with two regions
    (
        sequencing_upload_id_scripps,
        test_user_id_2,
        test_project_id_scripps,
        test_data_scripps,
    ) = _create_dummy_sequencing_upload(
        db_session, mocker, app, using_scripps="yes"
    )

    created_record_scripps = (
        db_session.query(SequencingUploadsTable)
        .filter_by(id=sequencing_upload_id_scripps)
        .first()
    )

    assert created_record_scripps.using_scripps is True
    assert created_record_scripps.region_1_forward_primer == "ITS3"
    assert created_record_scripps.region_1_reverse_primer == "ITS4"
    assert created_record_scripps.region_2_forward_primer == "WANDA"
    assert created_record_scripps.region_2_reverse_primer == "AML2"
    assert created_record_scripps.region_1 == "ITS2"
    assert created_record_scripps.region_2 == "SSU"
    assert (
        created_record_scripps.Sequencing_platform
        == "Element Biosciences AVITI"
    )
    assert created_record_scripps.Sequencing_regions_number == 2


def test_get_sequencing_upload(db_session, mocker):
    """
    Tests the retrieval of a SequencingUpload record
    and its derived properties.
    Inserts its own dummy User and Bucket records for self-sufficiency.
    """
    # Create dummy user and bucket for the primary get scenario
    dummy_user_id_get, dummy_project_id_get = (
        _create_dummy_user_and_bucket_dependencies(db_session)
    )

    # Create dummy user and bucket for the single region scenario
    dummy_user_id_single, dummy_project_id_single = (
        _create_dummy_user_and_bucket_dependencies(db_session)
    )

    # Mock helper methods within the SequencingUpload class
    mocker.patch.object(
        SequencingUpload,
        "determine_nr_files_per_sequence",
        side_effect=SequencingUpload.determine_nr_files_per_sequence,
    )
    mocker.patch.object(
        SequencingUpload, "get_region", side_effect=SequencingUpload.get_region
    )

    # 1. Create a dummy record directly in the database for retrieval
    initial_record_data = {
        "user_id": dummy_user_id_get,
        "project_id": dummy_project_id_get,
        "latest_metadata_filename": "dummy_meta_get.txt",
        "uploads_folder": "98765_20240501XYZABC",
        "Sequencing_platform": "Element Biosciences AVITI",
        "region_1": "RegionX",
        "region_2": "RegionY",
        "sequencing_upload_filedata": {"status": "processed", "reads": 1000},
        "using_scripps": False,
        "metadata_upload_confirmed": True,
        "files_uploading_confirmed": True,
        "Sequencing_regions_number": 2,
        "share_url": "http://share.url/test",
    }
    dummy_upload = SequencingUploadsTable(**initial_record_data)
    db_session.add(dummy_upload)
    db_session.commit()
    db_session.refresh(dummy_upload)

    # 2. Call the get method
    retrieved_data = SequencingUpload.get(dummy_upload.id)

    # 3. Assert the retrieved data
    assert retrieved_data is not None
    assert retrieved_data["id"] == dummy_upload.id
    assert retrieved_data["user_id"] == dummy_user_id_get
    assert retrieved_data["project_id"] == dummy_project_id_get
    assert retrieved_data["nr_files_per_sequence"] == 2
    assert retrieved_data["nr_regions"] == 2
    assert retrieved_data["regions"] == ["RegionX", "RegionY"]
    assert isinstance(retrieved_data["created_at"], datetime)

    # 4. Test getting a non-existent ID
    non_existent_id = dummy_upload.id + 999
    retrieved_data_none = SequencingUpload.get(non_existent_id)
    assert retrieved_data_none is None

    # 5. Test with a single region upload
    single_region_upload = SequencingUploadsTable(
        user_id=dummy_user_id_single,
        project_id=dummy_project_id_single,
        latest_metadata_filename="single.csv",
        uploads_folder="single_folder",
        Sequencing_platform="Other Platform",
        region_1="SingleRegionA",
        region_2=None,
        Sequencing_regions_number=1,
        sequencing_upload_filedata={},
        using_scripps=False,
    )
    db_session.add(single_region_upload)
    db_session.commit()
    db_session.refresh(single_region_upload)

    retrieved_single_region = SequencingUpload.get(single_region_upload.id)
    assert retrieved_single_region["nr_regions"] == 1
    assert retrieved_single_region["regions"] == ["SingleRegionA"]
    assert retrieved_single_region["nr_files_per_sequence"] == 1


def test_determine_nr_files_per_sequence():
    """
    Tests the static method determine_nr_files_per_sequence
    for various platforms.
    """
    # Platforms expecting 2 files (paired-end)
    assert (
        SequencingUpload.determine_nr_files_per_sequence("Illumina NextSeq")
        == 2
    )
    assert (
        SequencingUpload.determine_nr_files_per_sequence("Illumina MiSeq") == 2
    )
    assert (
        SequencingUpload.determine_nr_files_per_sequence("Illumina NovaSeq")
        == 2
    )
    assert (
        SequencingUpload.determine_nr_files_per_sequence(
            "Element Biosciences AVITI"
        )
        == 2
    )
    assert SequencingUpload.determine_nr_files_per_sequence("Other") == 2

    # Test with leading/trailing whitespace
    assert (
        SequencingUpload.determine_nr_files_per_sequence(" Illumina MiSeq ")
        == 2
    )
    assert SequencingUpload.determine_nr_files_per_sequence("Other ") == 2

    # Platforms expecting 1 file (single-end or unrecognized)
    assert (
        SequencingUpload.determine_nr_files_per_sequence("PacBio Sequel") == 1
    )
    assert (
        SequencingUpload.determine_nr_files_per_sequence(
            "Oxford Nanopore MinION"
        )
        == 1
    )
    assert (
        SequencingUpload.determine_nr_files_per_sequence("Unknown Platform")
        == 1
    )
    assert (
        SequencingUpload.determine_nr_files_per_sequence("A B C") == 1
    )  # Not in the list

    # Test with leading/trailing whitespace
    assert (
        SequencingUpload.determine_nr_files_per_sequence(
            " Oxford Nanopore MinION "
        )
        == 1
    )
    assert SequencingUpload.determine_nr_files_per_sequence(" A B C ") == 1


# The test function for SequencingUpload.get_region
def test_get_region():
    """
    Tests the get_region method of the SequencingUpload class by
    reading the actual primer_set_regions.json file.
    """
    # Test known primer sets (selected 5 as requested)
    assert SequencingUpload.get_region("ITS3", "ITS4") == "ITS2"
    assert SequencingUpload.get_region("WANDA", "AML2") == "SSU"
    assert SequencingUpload.get_region("ITS9mun", "ITS4ngsUni") == "Full_ITS"
    assert SequencingUpload.get_region("AML1", "AML2") == "SSU"
    assert SequencingUpload.get_region("LROR", "LR5") == "LSU"

    # Test for non-existent primer sets
    assert SequencingUpload.get_region("UNKNOWN_F", "UNKNOWN_R") is None
    assert SequencingUpload.get_region("ITS3", "NonExistent") is None
    assert SequencingUpload.get_region("NonExistent", "ITS4") is None
    assert SequencingUpload.get_region("", "") is None  # Empty primers


# New test function for SequencingUpload.get_regions
def test_get_regions():
    """
    Tests the get_regions method of the SequencingUpload class.
    This test relies on the actual primer_set_regions.json file.
    """
    # Test Case 1: One valid region
    regions = SequencingUpload.get_regions(
        region_1_forward_primer="ITS3", region_1_reverse_primer="ITS4"
    )
    assert regions == ["ITS2"]

    # Test Case 2: Two valid regions
    regions = SequencingUpload.get_regions(
        region_1_forward_primer="ITS3",
        region_1_reverse_primer="ITS4",
        region_2_forward_primer="WANDA",
        region_2_reverse_primer="AML2",
    )
    assert regions == ["ITS2", "SSU"]

    # Test Case 3: Region 1 with empty strings, Region 2 None
    regions = SequencingUpload.get_regions(
        region_1_forward_primer="", region_1_reverse_primer=""
    )
    assert regions == ["Other"]

    # Test Case 4: Region 1 valid, Region 2 empty strings
    regions = SequencingUpload.get_regions(
        region_1_forward_primer="ITS3",
        region_1_reverse_primer="ITS4",
        region_2_forward_primer="",
        region_2_reverse_primer="",
    )
    assert regions == ["ITS2", "Other"]

    # Test Case 5: Region 1 empty strings, Region 2 valid
    regions = SequencingUpload.get_regions(
        region_1_forward_primer="",
        region_1_reverse_primer="",
        region_2_forward_primer="WANDA",
        region_2_reverse_primer="AML2",
    )
    assert regions == ["Other", "SSU"]

    # Test Case 6: No regions provided (all None)
    regions = SequencingUpload.get_regions()
    assert regions == []

    # Test Case 7: Primers for Region 1 don't match, Region 2 valid
    regions = SequencingUpload.get_regions(
        region_1_forward_primer="NonExistentF",
        region_1_reverse_primer="NonExistentR",
        region_2_forward_primer="AML1",
        region_2_reverse_primer="AML2",
    )
    assert regions == ["SSU"]  # Only region 2 should be added

    # Test Case 8: Primers for Region 1 valid, Region 2 don't match
    regions = SequencingUpload.get_regions(
        region_1_forward_primer="ITS3",
        region_1_reverse_primer="ITS4",
        region_2_forward_primer="NonExistentF",
        region_2_reverse_primer="NonExistentR",
    )
    assert regions == ["ITS2"]  # Only region 1 should be added

    # Test Case 9: Only one primer provided
    # for a region (should not add region)
    regions = SequencingUpload.get_regions(
        region_1_forward_primer="ITS3",
        region_1_reverse_primer=None,  # Missing reverse primer
    )
    assert regions == []

    regions = SequencingUpload.get_regions(
        region_1_forward_primer=None,  # Missing forward primer
        region_1_reverse_primer="ITS4",
    )
    assert regions == []

    # Test Case 10: Using a real "Other" entry from the JSON (if it exists)
    regions = SequencingUpload.get_regions("Other", "Other")
    assert regions == ["Other"]


# Test function for SequencingUpload.get_samples
def test_get_samples(db_session, mocker, app):
    """
    Tests the get_samples method of the SequencingUpload class.
    Sets up a comprehensive scenario with multiple
    samples, OTUs, and analysis types.
    """
    # 1. Create a SequencingUpload record
    # (for the main sequencing_upload_id) using the helper
    sequencing_upload_id, user_id, project_id, _ = (
        _create_dummy_sequencing_upload(
            db_session,
            mocker,
            app,
            latest_metadata_filename="upload_meta.csv",
            sequencing_upload_filedata={"version": "1.0"},
            Country="USA",
            Sequencing_platform="Illumina NovaSeq",
            Sequencing_facility="University Lab",
            Expedition_lead="Dr. Smith",
            Collaborators="Team Delta",
            Extraction_method="Kit",
            Multiple_sequencing_runs="No",
            DNA_conc_instrument="NanoDrop",
            files_uploading_confirmed=True,
            share_url=None,
            share_sync_completed=False,
            region_1_forward_primer="ITS3",  # Explicitly set primers
            region_1_reverse_primer="ITS4",
            region_2_forward_primer="0",
            region_2_reverse_primer="0",
        )
    )

    # 2. Create a SECOND SequencingUpload record
    # (for sample_3 to reference) using the helper
    sequencing_upload_id_2, user_id_2, project_id_2, _ = (
        _create_dummy_sequencing_upload(
            db_session,
            mocker,
            app,
            latest_metadata_filename="upload_meta_2.csv",
        )
    )

    # 3. Create dummy ResolveEcoregionsTable entries using the helper
    ecoregion_1 = _create_dummy_ecoregion(
        db_session, 1, "Forest", fid=100, objectid=200
    )
    ecoregion_2 = _create_dummy_ecoregion(
        db_session, 2, "Desert", fid=101, objectid=201
    )

    # 4. Create dummy SequencingAnalysisTypesTable entries
    analysis_type_1 = SequencingAnalysisTypesTable(id=101, name="16S")
    analysis_type_2 = SequencingAnalysisTypesTable(id=102, name="ITS")
    analysis_type_3 = SequencingAnalysisTypesTable(id=103, name="COI")
    db_session.add_all([analysis_type_1, analysis_type_2, analysis_type_3])
    db_session.commit()

    # 5. Create dummy SequencingSamplesTable
    # entries (using SampleID and Site_name)
    sample_1 = SequencingSamplesTable(
        id=1001,
        sequencingUploadId=sequencing_upload_id,  # Linked to the first upload
        resolve_ecoregion_id=ecoregion_1.id,
        SampleID="Sample_A_ID",
        Site_name="Site_A_Name",
    )
    sample_2 = SequencingSamplesTable(
        id=1002,
        sequencingUploadId=sequencing_upload_id,
        resolve_ecoregion_id=ecoregion_2.id,
        SampleID="Sample_B_ID",
        Site_name="Site_B_Name",
    )
    sample_3 = SequencingSamplesTable(
        id=1003,
        sequencingUploadId=sequencing_upload_id_2,
        resolve_ecoregion_id=ecoregion_1.id,
        SampleID="Sample_C_Other_Upload_ID",
        Site_name="Site_C_Name",
    )
    sample_4_no_ecoregion = SequencingSamplesTable(
        id=1004,
        sequencingUploadId=sequencing_upload_id,
        resolve_ecoregion_id=None,
        SampleID="Sample_D_No_Ecoregion_ID",
        Site_name="Site_D_Name",
    )
    sample_5_no_otus = SequencingSamplesTable(
        id=1005,
        sequencingUploadId=sequencing_upload_id,  # Linked to the first upload
        resolve_ecoregion_id=ecoregion_1.id,
        SampleID="Sample_E_No_OTUs_ID",
        Site_name="Site_E_Name",
    )
    db_session.add_all(
        [sample_1, sample_2, sample_3, sample_4_no_ecoregion, sample_5_no_otus]
    )
    db_session.commit()

    # 6. Create dummy Taxonomy entries using the helper
    tax_1 = _create_dummy_taxonomy_hierarchy(
        db_session,
        taxonomy_id=2001,
        domain_name="Bacteria",
        phylum_name="Firmicutes",
        class_name="Bacilli",
        order_name="Bacillales",
        family_name="Bacillaceae",
        genus_name="Bacillus",
        species_name="subtilis",
    )
    tax_2 = _create_dummy_taxonomy_hierarchy(
        db_session,
        taxonomy_id=2002,
        domain_name="Eukaryota",
        phylum_name="Ascomycota",
        class_name="Saccharomycetes",
        order_name="Saccharomycetales",
        family_name="Saccharomycetaceae",
        genus_name="Saccharomyces",
        species_name="cerevisiae",
    )
    tax_3 = _create_dummy_taxonomy_hierarchy(
        db_session,
        taxonomy_id=2003,
        domain_name="Archaea",
        phylum_name="Euryarchaeota",
        class_name="Methanomicrobia",
        order_name="Methanosarcinales",
        family_name="Methanosarcinaceae",
        genus_name="Methanosarcina",
        species_name="barkeri",
    )

    # 7. Create dummy SequencingAnalysisTable entries
    analysis_16s_1 = SequencingAnalysisTable(
        id=3001, sequencingAnalysisTypeId=analysis_type_1.id
    )
    analysis_its_1 = SequencingAnalysisTable(
        id=3002, sequencingAnalysisTypeId=analysis_type_2.id
    )
    analysis_coi_1 = SequencingAnalysisTable(
        id=3003, sequencingAnalysisTypeId=analysis_type_3.id
    )
    analysis_16s_2 = SequencingAnalysisTable(
        id=3004, sequencingAnalysisTypeId=analysis_type_1.id
    )
    db_session.add_all(
        [analysis_16s_1, analysis_its_1, analysis_coi_1, analysis_16s_2]
    )
    db_session.commit()

    # 8. Create dummy OTU entries
    db_session.add(
        OTU(
            id=4001,
            sample_id=sample_1.id,
            taxonomy_id=tax_1.id,
            sequencing_analysis_id=analysis_16s_1.id,
        )
    )
    db_session.add(
        OTU(
            id=4002,
            sample_id=sample_1.id,
            taxonomy_id=tax_2.id,
            sequencing_analysis_id=analysis_16s_1.id,
        )
    )
    db_session.add(
        OTU(
            id=4003,
            sample_id=sample_1.id,
            taxonomy_id=tax_3.id,
            sequencing_analysis_id=analysis_its_1.id,
        )
    )
    db_session.add(
        OTU(
            id=4004,
            sample_id=sample_1.id,
            taxonomy_id=tax_1.id,
            sequencing_analysis_id=analysis_its_1.id,
        )
    )
    db_session.add(
        OTU(
            id=4005,
            sample_id=sample_2.id,
            taxonomy_id=tax_2.id,
            sequencing_analysis_id=analysis_16s_2.id,
        )
    )
    db_session.add(
        OTU(
            id=4006,
            sample_id=sample_2.id,
            taxonomy_id=tax_3.id,
            sequencing_analysis_id=analysis_coi_1.id,
        )
    )
    db_session.add(
        OTU(
            id=4007,
            sample_id=sample_2.id,
            taxonomy_id=tax_1.id,
            sequencing_analysis_id=analysis_coi_1.id,
        )
    )
    db_session.commit()

    # 9. Call the method under test
    samples_returned = SequencingUpload.get_samples(sequencing_upload_id)

    # 10. Assertions (using SampleID and Site_name)
    assert isinstance(samples_returned, list)
    assert len(samples_returned) == 4

    returned_sample_1 = next(
        (s for s in samples_returned if s["id"] == sample_1.id), None
    )
    returned_sample_2 = next(
        (s for s in samples_returned if s["id"] == sample_2.id), None
    )
    returned_sample_4 = next(
        (s for s in samples_returned if s["id"] == sample_4_no_ecoregion.id),
        None,
    )
    returned_sample_5 = next(
        (s for s in samples_returned if s["id"] == sample_5_no_otus.id), None
    )

    assert returned_sample_1 is not None
    assert returned_sample_1["SampleID"] == "Sample_A_ID"
    assert returned_sample_1["Site_name"] == "Site_A_Name"
    assert returned_sample_1["ResolveEcoregion"] == "Forest"
    assert returned_sample_1["otu_counts"] == {
        analysis_type_1.id: {"name": "16S", "count": 2},
        analysis_type_2.id: {"name": "ITS", "count": 2},
    }

    assert returned_sample_2 is not None
    assert returned_sample_2["SampleID"] == "Sample_B_ID"
    assert returned_sample_2["Site_name"] == "Site_B_Name"
    assert returned_sample_2["ResolveEcoregion"] == "Desert"
    assert returned_sample_2["otu_counts"] == {
        analysis_type_1.id: {"name": "16S", "count": 1},
        analysis_type_3.id: {"name": "COI", "count": 2},
    }

    assert returned_sample_4 is not None
    assert returned_sample_4["SampleID"] == "Sample_D_No_Ecoregion_ID"
    assert returned_sample_4["Site_name"] == "Site_D_Name"
    assert returned_sample_4["ResolveEcoregion"] is None
    assert returned_sample_4["otu_counts"] == {}

    assert returned_sample_5 is not None
    assert returned_sample_5["SampleID"] == "Sample_E_No_OTUs_ID"
    assert returned_sample_5["Site_name"] == "Site_E_Name"
    assert returned_sample_5["otu_counts"] == {}

    samples_no_results = SequencingUpload.get_samples(
        sequencing_upload_id_2 + 1
    )
    assert samples_no_results == []
