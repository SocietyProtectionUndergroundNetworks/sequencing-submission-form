import docker
import pandas as pd
import logging
import json
import time
from helpers.dbm import session_scope
from models.db_model import ResolveEcoregionsTable, ExternalSamplingTable

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")


def import_ecoregions_from_csv(csv_file_path):
    try:
        # Read the CSV file into a pandas DataFrame
        df = pd.read_csv(
            csv_file_path, dtype=str
        )  # Read as strings to avoid unexpected conversions

        # Convert necessary columns to the appropriate types
        df = df.astype(
            {
                "FID": "Int64",
                "OBJECTID": "Int64",
                "Biome number": "Int64",
                "Nature Needs Half number": "Int64",
                "Ecoregion unique ID": "Int64",
                "SHAPE_LENG": "float64",
                "Shape__Area": "float64",
                "Shape__Length": "float64",
            },
            errors="ignore",
        )  # Ignore errors to prevent crashes on conversion failures

        # Replace NaN values with None (SQL NULL)
        df = df.where(pd.notna(df), None)

        # Rename columns to match the database model
        df.rename(
            columns={
                "Ecoregion name": "ecoregion_name",
                "Biome number": "biome_number",
                "Biome name": "biome_name",
                "Realm name": "realm_name",
                "Ecoregion Biome": "ecoregion_biome",
                "Nature Needs Half number": "nature_needs_half_number",
                "Ecoregion unique ID": "ecoregion_unique_id",
                "SHAPE_LENG": "shape_leng",
                "Nature Needs Half description": (
                    "nature_needs_half_description"
                ),
                "Color": "color",
                "Biome color": "biome_color",
                "Nature Needs Half color": "nature_needs_half_color",
                "License": "license",
                "Shape__Area": "shape_area",
                "Shape__Length": "shape_length",
            },
            inplace=True,
        )

        # Convert DataFrame rows into list of ResolveEcoregionsTable objects
        records = df.to_dict(orient="records")
        ecoregions = [ResolveEcoregionsTable(**row) for row in records]

        with session_scope() as session:
            # Check if the OBJECTID = 0 record already exists
            existing_zero_objectid = (
                session.query(ResolveEcoregionsTable)
                .filter_by(OBJECTID=0)
                .first()
            )

            # If it doesn't exist, create it
            if not existing_zero_objectid:
                zero_ecoregion = ResolveEcoregionsTable(
                    OBJECTID=0,
                    FID=0,
                    ecoregion_name="Unknown",
                    biome_number=None,
                    biome_name=None,
                    realm_name=None,
                    ecoregion_biome=None,
                    nature_needs_half_number=None,
                    ecoregion_unique_id=None,
                    shape_leng=None,
                    nature_needs_half_description=None,
                    color=None,
                    biome_color=None,
                    nature_needs_half_color=None,
                    license=None,
                    shape_area=None,
                    shape_length=None,
                )
                session.add(zero_ecoregion)

            # Bulk insert the other ecoregions
            session.bulk_save_objects(ecoregions)
            logger.info("Import successful!")

    except Exception as e:
        logger.error(f"Error importing data: {e}", exc_info=True)


def return_ecoregion(coordinates_list=None):
    logger.info("Getting local resolve ecoregions for")
    logger.info(coordinates_list)
    if not coordinates_list:
        logger.error("No coordinates provided.")
        return None

    client = docker.from_env()
    container = client.containers.get("spun-geopandas")

    # Construct the command_str dynamically
    coordinates_str = " ".join(
        [f"{lat} {lon}" for lat, lon in coordinates_list]
    )
    command_str = f"python app.py {coordinates_str}"

    result = container.exec_run(["bash", "-c", command_str])

    # logger.info(result.output.decode())
    return result.output.decode()


def init_update_external_samples_with_ecoregions():
    from tasks import update_external_samples_with_ecoregions_async

    update_external_samples_with_ecoregions_async.delay()


def update_external_samples_with_ecoregions():
    with session_scope() as session:
        # Get the ecoregion ID for OBJECTID = 0
        zero_ecoregion = (
            session.query(ResolveEcoregionsTable.id)
            .filter_by(OBJECTID=0)
            .first()
        )

        if not zero_ecoregion:
            logger.error(
                "Ecoregion with OBJECTID = 0 is missing from the database."
            )
            return

        zero_ecoregion_id = zero_ecoregion.id

        while True:
            # Get one coordinate where resolve_ecoregion_id is NULL
            coordinate = (
                session.query(
                    ExternalSamplingTable.latitude,
                    ExternalSamplingTable.longitude,
                )
                .filter(ExternalSamplingTable.resolve_ecoregion_id.is_(None))
                .distinct()
                .first()
            )

            if not coordinate:
                logger.info("No more coordinates to process.")
                break  # Exit when there are no more samples to update

            lat, lon = coordinate.latitude, coordinate.longitude
            result = return_ecoregion(
                [(lat, lon)]
            )  # Get ecoregion for the coordinate

            try:
                ecoregion_data = json.loads(result)
                objectid = ecoregion_data.get("OBJECTID")
            except (json.JSONDecodeError, TypeError):
                logger.error(
                    f"Failed to parse ecoregion "
                    f"result for {lat}, {lon}: {result}"
                )
                objectid = None

            if objectid is None:
                resolve_ecoregion_id = (
                    zero_ecoregion_id  # Assign OBJECTID = 0 ecoregion
                )
            else:
                # Find the resolve_ecoregions ID corresponding to the OBJECTID
                resolve_ecoregion = (
                    session.query(ResolveEcoregionsTable.id)
                    .filter_by(OBJECTID=objectid)
                    .first()
                )
                resolve_ecoregion_id = (
                    resolve_ecoregion.id
                    if resolve_ecoregion
                    else zero_ecoregion_id
                )

            # Update all records with this coordinate
            session.query(ExternalSamplingTable).filter_by(
                latitude=lat, longitude=lon, resolve_ecoregion_id=None
            ).update({"resolve_ecoregion_id": resolve_ecoregion_id})

            session.commit()
            logger.info(
                f"Updated {lat}, {lon} with "
                f" ecoregion ID {resolve_ecoregion_id}"
            )

            time.sleep(
                0.2
            )  # Wait 0.2 second before processing the next coordinate


def import_ecoregions_from_csv_its(csv_file_path):
    try:
        # Read the CSV file into a pandas DataFrame
        df = pd.read_csv(csv_file_path, dtype=str)

        # Select only the required columns and rename them
        df = df.rename(
            columns={
                "PermanentID": "sample_id",
                "latitude": "latitude",
                "longitude": "longitude",
            }
        )

        # Drop any rows where required columns are missing
        df = df[["sample_id", "latitude", "longitude"]].dropna()

        with session_scope() as session:
            imported_count = 0  # Track the number of new records added

            for _, row in df.iterrows():
                # Check if the sample already exists in the database
                exists = (
                    session.query(ExternalSamplingTable)
                    .filter_by(
                        sample_id=row["sample_id"],
                        latitude=row["latitude"],
                        longitude=row["longitude"],
                        dna_region="ITS",
                    )
                    .first()
                )

                if not exists:  # Insert only if it does not exist
                    new_sample = ExternalSamplingTable(
                        sample_id=row["sample_id"],
                        latitude=row["latitude"],
                        longitude=row["longitude"],
                        dna_region="ITS",
                    )
                    session.add(new_sample)
                    imported_count += 1  # Increment count for new insertions

            session.commit()

        logger.info(
            f"External samples import successful! "
            f" New records added: {imported_count}"
        )
        return {"status": "success", "imported_records": imported_count}

    except Exception as e:
        logger.error(f"Error importing external samples: {e}")
        return {"status": "error", "message": str(e)}


def import_ecoregions_from_csv_ssu(csv_file_path):
    try:
        # Read the CSV file into a pandas DataFrame
        df = pd.read_csv(csv_file_path, dtype=str)

        # Select only the required columns and rename them
        df = df.rename(
            columns={
                "sample_ID": "sample_id",
                "latitude": "latitude",
                "longitude": "longitude",
            }
        )

        # Drop any rows where required columns are missing
        df = df[["sample_id", "latitude", "longitude"]].dropna()

        with session_scope() as session:
            imported_count = 0  # Track the number of new records added

            for _, row in df.iterrows():
                # Check if the sample already exists in the database
                exists = (
                    session.query(ExternalSamplingTable)
                    .filter_by(
                        sample_id=row["sample_id"],
                        latitude=row["latitude"],
                        longitude=row["longitude"],
                        dna_region="SSU",
                    )
                    .first()
                )

                if not exists:  # Insert only if it does not exist
                    new_sample = ExternalSamplingTable(
                        sample_id=row["sample_id"],
                        latitude=row["latitude"],
                        longitude=row["longitude"],
                        dna_region="ITS",
                    )
                    session.add(new_sample)
                    imported_count += 1  # Increment count for new insertions

            session.commit()

        logger.info(
            f"External samples import successful! "
            f"New records added: {imported_count}"
        )
        return {"status": "success", "imported_records": imported_count}

    except Exception as e:
        logger.error(f"Error importing external samples: {e}")
        return {"status": "error", "message": str(e)}
