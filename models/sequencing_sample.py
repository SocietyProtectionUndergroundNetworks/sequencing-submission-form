import logging
from helpers.dbm import connect_db, get_session
from helpers.land_use import get_land_use, get_resolve_ecoregion, get_baileys_ecoregion, get_elevation
from models.db_model import SequencingSamplesTable
from sqlalchemy import or_

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")


class SequencingSample:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload_db = (
            session.query(SequencingSamplesTable).filter_by(id=id).first()
        )

        session.close()

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
        db_engine = connect_db()
        session = get_session(db_engine)

        # Convert 'yes'/'no' to boolean for specific field
        datadict = {
            k: (v.lower() == "yes") if k == "using_scripps" else v
            for k, v in datadict.items()
        }

        # Get valid columns from the table's model class
        valid_keys = {c.name for c in SequencingSamplesTable.__table__.columns}

        # Filter out valid keys to create the filtered data dictionary
        filtered_datadict = {
            key: value for key, value in datadict.items() if key in valid_keys
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
            session.close()
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

        session.close()

        return new_sample_id

    @classmethod
    def update_missing_fields(self):
        db_engine = connect_db()
        session = get_session(db_engine)

        samples_to_update = (
            session.query(SequencingSamplesTable)
            .filter(
                or_(
                    SequencingSamplesTable.Elevation.is_(None),
                    SequencingSamplesTable.Elevation == "",
                    SequencingSamplesTable.Land_use.is_(None),
                    SequencingSamplesTable.Land_use == "",
                    SequencingSamplesTable.ResolveEcoregion.is_(None),
                    SequencingSamplesTable.ResolveEcoregion == "",
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
            )
            .limit(30)
            .all()
        )

        for sample in samples_to_update:
            logger.info(sample.SampleID)
            latitude_str = sample.Latitude
            longitude_str = sample.Longitude

            # Check if Latitude and Longitude are
            # valid float-convertible strings
            if latitude_str and longitude_str:
                try:
                    latitude = float(latitude_str)
                    longitude = float(longitude_str)

                    # Skip if Latitude or Longitude are still invalid or 'nan'
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
                    # (Land_use, ResolveEcoregion, BaileysEcoregion, Elevation)
                    if not sample.Land_use:
                        land_use = get_land_use(longitude, latitude)
                        if land_use:
                            sample.Land_use = land_use
                            logger.info(
                                f"Updated Land_use for SampleID"
                                f" {sample.SampleID} with {land_use}"
                            )

                    if not sample.ResolveEcoregion:
                        ecoregion = get_resolve_ecoregion(longitude, latitude)
                        if ecoregion:
                            sample.ResolveEcoregion = ecoregion
                            logger.info(
                                f"Updated Resolve Ecoregion for SampleID"
                                f" {sample.SampleID} with {ecoregion}"
                            )

                    if not sample.BaileysEcoregion:
                        ecoregion = get_baileys_ecoregion(longitude, latitude)
                        if ecoregion:
                            sample.BaileysEcoregion = ecoregion
                            logger.info(
                                f"Updated Resolve Ecoregion for SampleID"
                                f" {sample.SampleID} with {ecoregion}"
                            )

                    if not sample.Elevation:
                        elevation = get_elevation(longitude, latitude)
                        if elevation:
                            sample.Elevation = elevation
                            logger.info(
                                f"Updated Elevation for SampleID"
                                f" {sample.SampleID} with {elevation}"
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

        session.close()
