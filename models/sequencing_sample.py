import logging
from helpers.dbm import session_scope
from helpers.land_use import (
    get_land_use,
    get_baileys_ecoregion,
    get_elevation,
)
from helpers.ecoregions import get_resolve_ecoregion_objectid
from models.db_model import SequencingSamplesTable, OTU, ResolveEcoregionsTable
from sqlalchemy import or_, select
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import func

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")


class SequencingSample:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        with session_scope() as session:

            upload_db = (
                session.query(SequencingSamplesTable).filter_by(id=id).first()
            )

            if not upload_db:
                return None

            # Assuming upload_db is an instance of some SQLAlchemy model
            upload_db_dict = upload_db.__dict__

            # Remove keys starting with '_'
            filtered_dict = {
                key: value
                for key, value in upload_db_dict.items()
                if not key.startswith("_")
            }

            # Create an instance of YourClass using the dictionary
            upload = SequencingSamplesTable(**filtered_dict)

            return upload

    @classmethod
    def create(cls, sequencingUploadId, datadict):
        with session_scope() as session:

            # Convert 'yes'/'no' to boolean for specific field
            datadict = {
                k: (v.lower() == "yes") if k == "using_scripps" else v
                for k, v in datadict.items()
            }

            # Get valid columns from the table's model class
            valid_keys = {
                c.name for c in SequencingSamplesTable.__table__.columns
            }

            # Filter out valid keys to create the filtered data dictionary
            filtered_datadict = {
                key: value
                for key, value in datadict.items()
                if key in valid_keys
            }

            # Identify the extra columns
            extra_columns = {
                key: value
                for key, value in datadict.items()
                if key not in valid_keys
            }

            # Include sequencingUploadId in the filters
            filters = [
                getattr(SequencingSamplesTable, key) == value
                for key, value in filtered_datadict.items()
            ]
            filters.append(
                SequencingSamplesTable.sequencingUploadId == sequencingUploadId
            )

            # Query to check if identical record exists
            existing_record = (
                session.query(SequencingSamplesTable).filter(*filters).first()
            )

            if existing_record:
                return existing_record.id

            # If no existing record is found, create a new one
            new_sample = SequencingSamplesTable(
                sequencingUploadId=sequencingUploadId,
            )

            for key, value in filtered_datadict.items():
                if hasattr(new_sample, key):
                    setattr(new_sample, key, value)

            # Add extra columns to the extracolumns_json field as JSON
            if extra_columns:
                new_sample.extracolumns_json = extra_columns

            session.add(new_sample)
            session.commit()

            session.refresh(new_sample)

            new_sample_id = new_sample.id

            return new_sample_id

    @classmethod
    def update(cls, sample_id, datadict):
        with session_scope() as session:
            try:
                sample = (
                    session.query(SequencingSamplesTable)
                    .filter_by(id=sample_id)
                    .one()
                )

                # Convert 'yes'/'no' to boolean for specific field
                datadict = {
                    k: (v.lower() == "yes") if k == "using_scripps" else v
                    for k, v in datadict.items()
                }

                # Get valid columns from the table's model class
                valid_keys = {
                    c.name for c in SequencingSamplesTable.__table__.columns
                }

                # Filter out valid keys to create the filtered data dictionary
                filtered_datadict = {
                    key: value
                    for key, value in datadict.items()
                    if key in valid_keys
                }

                for key, value in filtered_datadict.items():
                    if hasattr(sample, key):
                        setattr(sample, key, value)

                session.commit()
                return True  # Indicate successful update
            except NoResultFound:
                return False  # sample not found
            except Exception as e:
                print(f"Error updating sample: {e}")
                session.rollback()
                return False  # indicate failure

    @classmethod
    def update_missing_fields(self):
        with session_scope() as session:

            samples_to_update_query = (
                session.query(SequencingSamplesTable)
                .filter(
                    or_(
                        SequencingSamplesTable.Elevation.is_(None),
                        SequencingSamplesTable.Elevation == "",
                        SequencingSamplesTable.Land_use.is_(None),
                        SequencingSamplesTable.Land_use == "",
                        SequencingSamplesTable.BaileysEcoregion.is_(None),
                        SequencingSamplesTable.BaileysEcoregion == "",
                    ),
                    # Ensuring Latitude and Longitude are valid
                    # and not empty or 'nan'
                    SequencingSamplesTable.Latitude.isnot(None),
                    SequencingSamplesTable.Latitude != "",
                    SequencingSamplesTable.Longitude.isnot(None),
                    SequencingSamplesTable.Longitude != "",
                    SequencingSamplesTable.Latitude != "nan",
                    SequencingSamplesTable.Longitude != "nan",
                    SequencingSamplesTable.Sample_or_Control == "True sample",
                    # Additional conditions to exclude '-' values or NULL
                    # for BaileysEcoregion
                    or_(
                        SequencingSamplesTable.BaileysEcoregion != "-",
                        SequencingSamplesTable.BaileysEcoregion.is_(None),
                    ),
                    or_(
                        SequencingSamplesTable.Agricultural_land != "Yes",
                        SequencingSamplesTable.resolve_ecoregion_id.is_(None),
                    ),
                )
                .limit(50)
            )

            # Fetch the results after logging the query
            samples_to_update = samples_to_update_query.all()

            for sample in samples_to_update:
                logger.info("###############################")
                logger.info("Doing " + sample.SampleID)
                latitude_str = sample.Latitude
                longitude_str = sample.Longitude

                # Check if Latitude and Longitude are
                # valid float-convertible strings
                if latitude_str and longitude_str:
                    try:
                        latitude = float(latitude_str)
                        longitude = float(longitude_str)

                        # Skip if Latitude or Longitude are still
                        # invalid or 'nan'
                        if (
                            latitude == 0 or longitude == 0
                        ):  # Skip if Latitude or Longitude are (0,0)
                            logger.error(
                                f"Invalid Latitude or Longitude for SampleID "
                                f" {sample.SampleID}: "
                                f" Latitude={latitude}, Longitude={longitude}"
                            )
                            continue

                        # Proceed with getting the missing fields
                        # (Land_use, resolve_ecoregion_id,
                        # BaileysEcoregion, Elevation)
                        if not sample.Land_use:
                            logger.info(" - Missing Land_use")
                            land_use = get_land_use(longitude, latitude)
                            if land_use:
                                sample.Land_use = land_use
                                logger.info(
                                    f"Updated Land_use for SampleID"
                                    f" {sample.SampleID} with {land_use}"
                                )
                            else:
                                sample.Land_use = "-"
                                logger.info(
                                    f"Updated Land_use for SampleID"
                                    f" {sample.SampleID} with '-'"
                                )
                        if not sample.resolve_ecoregion_id:
                            logger.info(" - Missing ResolveEcoregion")
                            ecoregion_object_id = (
                                get_resolve_ecoregion_objectid(
                                    longitude, latitude
                                )
                            )

                            resolve_ecoregion = (
                                session.query(ResolveEcoregionsTable.id)
                                .filter_by(OBJECTID=ecoregion_object_id)
                                .first()
                            )
                            if resolve_ecoregion:
                                sample.resolve_ecoregion_id = (
                                    resolve_ecoregion.id
                                )
                                logger.info(
                                    f"Updated Resolve Ecoregion for SampleID"
                                    f" {sample.SampleID} with "
                                    f" {resolve_ecoregion.id}"
                                )
                            else:
                                zero_ecoregion = (
                                    session.query(ResolveEcoregionsTable.id)
                                    .filter_by(OBJECTID=0)
                                    .first()
                                )
                                sample.resolve_ecoregion_id = zero_ecoregion.id
                                logger.info(
                                    f"Updated Resolve Ecoregion for SampleID"
                                    f" {sample.SampleID} with "
                                    f" {zero_ecoregion.id}"
                                )

                        if not sample.BaileysEcoregion:
                            logger.info(" - Missing BaileysEcoregion")
                            ecoregion = get_baileys_ecoregion(
                                longitude, latitude
                            )
                            if ecoregion:
                                sample.BaileysEcoregion = ecoregion
                                logger.info(
                                    f"Updated Baileys Ecoregion for SampleID"
                                    f" {sample.SampleID} with {ecoregion}"
                                )
                            else:
                                sample.BaileysEcoregion = "-"
                                logger.info(
                                    f"Updated Baileys Ecoregion for SampleID"
                                    f" {sample.SampleID} with '-'"
                                )

                        if not sample.Elevation:
                            logger.info(" - Missing Elevation")
                            elevation = get_elevation(longitude, latitude)
                            if elevation:
                                sample.Elevation = elevation
                                logger.info(
                                    f"Updated Elevation for SampleID"
                                    f" {sample.SampleID} with {elevation}"
                                )
                            else:
                                sample.Elevation = "-"
                                logger.info(
                                    f"Updated Elevation for SampleID"
                                    f" {sample.SampleID} with '-'"
                                )
                        # Commit the changes
                        session.commit()
                        logger.info(
                            f"Successfully updated SampleID {sample.SampleID}"
                        )

                    except ValueError:
                        # Latitude or Longitude is not a valid float
                        logger.error(
                            f"Invalid Latitude or Longitude for SampleID"
                            f"{sample.SampleID}: Latitude={latitude_str},"
                            f" Longitude={longitude_str}"
                        )
                        continue
                else:
                    # Skip if Latitude or Longitude are empty or None
                    logger.error(
                        f"Missing Latitude or Longitude "
                        f" for SampleID {sample.SampleID}"
                    )
                    continue

    @classmethod
    def count_missing_fields(cls):
        with session_scope() as session:
            count_query = session.query(
                func.count(SequencingSamplesTable.id)
            ).filter(  # Counting rows
                or_(
                    SequencingSamplesTable.Elevation.is_(None),
                    SequencingSamplesTable.Elevation == "",
                    SequencingSamplesTable.Land_use.is_(None),
                    SequencingSamplesTable.Land_use == "",
                    SequencingSamplesTable.BaileysEcoregion.is_(None),
                    SequencingSamplesTable.BaileysEcoregion == "",
                ),
                SequencingSamplesTable.Latitude.isnot(None),
                SequencingSamplesTable.Latitude != "",
                SequencingSamplesTable.Longitude.isnot(None),
                SequencingSamplesTable.Longitude != "",
                SequencingSamplesTable.Latitude != "nan",
                SequencingSamplesTable.Longitude != "nan",
                SequencingSamplesTable.Sample_or_Control == "True sample",
                or_(
                    SequencingSamplesTable.BaileysEcoregion != "-",
                    SequencingSamplesTable.BaileysEcoregion.is_(None),
                ),
                or_(
                    SequencingSamplesTable.Agricultural_land != "Yes",
                    SequencingSamplesTable.resolve_ecoregion_id.is_(None),
                ),
            )

            count_result = count_query.scalar()  # Returns the count directly
            return count_result

    @classmethod
    def assign_taxonomy(cls, sample_id, taxonomy_id, abundance):
        with session_scope() as session:

            # Check if the OTU combination already exists
            existing_otu = (
                session.query(OTU)
                .filter(
                    OTU.sample_id == sample_id, OTU.taxonomy_id == taxonomy_id
                )
                .first()
            )

            if existing_otu:
                # If it exists, update the abundance
                existing_otu.abundance = abundance
                session.commit()
                logger.info(
                    f"Updated abundance for sample {sample_id} "
                    f"and taxonomy {taxonomy_id}."
                )
            else:
                # If not, create a new OTU record
                new_otu = OTU(
                    sample_id=sample_id,
                    taxonomy_id=taxonomy_id,
                    abundance=abundance,
                )
                session.add(new_otu)
                session.commit()
                logger.info(
                    f"Assigned new taxonomy {taxonomy_id} to "
                    f"sample {sample_id} with abundance {abundance}."
                )

    @classmethod
    def get_analysis_types_with_otus(cls, sample_id):
        from models.db_model import (
            SequencingAnalysisTypesTable,
            OTU,
            SequencingAnalysisTable,
        )

        with session_scope() as session:
            query = (
                select(
                    SequencingAnalysisTypesTable.name,
                    SequencingAnalysisTypesTable.id,
                )
                .join(
                    SequencingAnalysisTable,
                    SequencingAnalysisTypesTable.id
                    == SequencingAnalysisTable.sequencingAnalysisTypeId,
                )
                .join(
                    OTU,
                    SequencingAnalysisTable.id == OTU.sequencing_analysis_id,
                )
                .where(OTU.sample_id == sample_id)
                .group_by(
                    SequencingAnalysisTypesTable.name,
                    SequencingAnalysisTypesTable.id,
                )
            )

            result = session.execute(query).all()
            return [(row.name, row.id) for row in result]
