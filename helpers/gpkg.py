import docker
import json
import logging
import uuid
import os
import io
from collections import defaultdict

from helpers.dbm import session_scope
from models.db_model import (
    SequencingUploadsTable,
    SequencingSamplesTable,
    SequencingSequencerIDsTable,
    SequencingAnalysisTable,
    SequencingAnalysisSampleRichnessTable,
)

logger = logging.getLogger("my_app_logger")

# Paths as seen from the Flask container and the geopandas container
_FLASK_GEOPANDAS_DIR = "/app/geopandasapp"
_GEOPANDAS_CONTAINER_DIR = "/geopandasapp"


def create_samples_gpkg():
    """
    Query sequencing_uploads and sequencing_samples, delegate .gpkg creation
    to the geopandas container, and return the file contents as a BytesIO.
    Returns None on failure.
    """
    with session_scope() as session:
        rows = (
            session.query(SequencingSamplesTable, SequencingUploadsTable)
            .join(
                SequencingUploadsTable,
                SequencingSamplesTable.sequencingUploadId
                == SequencingUploadsTable.id,
            )
            .filter(
                SequencingSamplesTable.Latitude.isnot(None),
                SequencingSamplesTable.Longitude.isnot(None),
                SequencingSamplesTable.Latitude != "",
                SequencingSamplesTable.Longitude != "",
                SequencingSamplesTable.Latitude != "nan",
                SequencingSamplesTable.Longitude != "nan",
            )
            .all()
        )

        sample_ids = [sample.id for sample, _ in rows]

        # Distinct DNA regions per sample
        region_rows = (
            session.query(
                SequencingSequencerIDsTable.sequencingSampleId,
                SequencingSequencerIDsTable.Region,
            )
            .filter(
                SequencingSequencerIDsTable.sequencingSampleId.in_(sample_ids),
                SequencingSequencerIDsTable.Region.isnot(None),
            )
            .distinct()
            .all()
        )

        regions_by_sample = defaultdict(set)
        for r in region_rows:
            regions_by_sample[r.sequencingSampleId].add(r.Region)

        # Richness data for sequencingAnalysisTypeId = 1, latest analysis per sample
        richness_rows = (
            session.query(SequencingAnalysisSampleRichnessTable)
            .join(
                SequencingAnalysisTable,
                SequencingAnalysisSampleRichnessTable.analysis_id
                == SequencingAnalysisTable.id,
            )
            .filter(
                SequencingAnalysisTable.sequencingAnalysisTypeId == 1,
                SequencingAnalysisSampleRichnessTable.sample_id.in_(
                    sample_ids
                ),
            )
            .order_by(SequencingAnalysisSampleRichnessTable.analysis_id.desc())
            .all()
        )

        richness_by_sample = {}
        for r in richness_rows:
            if r.sample_id not in richness_by_sample:
                richness_by_sample[r.sample_id] = r

        data = []
        for sample, upload in rows:
            regions = regions_by_sample.get(sample.id, set())
            richness = richness_by_sample.get(sample.id)

            data.append(
                {
                    # Upload-level fields
                    "upload_id": upload.id,
                    "project_id": upload.project_id,
                    "Country": upload.Country,
                    "Sequencing_platform": upload.Sequencing_platform,
                    "Sequencing_facility": upload.Sequencing_facility,
                    "Expedition_lead": upload.Expedition_lead,
                    "Collaborators": upload.Collaborators,
                    "region_1": upload.region_1,
                    "region_2": upload.region_2,
                    "Extraction_method": upload.Extraction_method,
                    # Sample-level fields
                    "sample_db_id": sample.id,
                    "SampleID": sample.SampleID,
                    "Site_name": sample.Site_name,
                    "Latitude": sample.Latitude,
                    "Longitude": sample.Longitude,
                    "Vegetation": sample.Vegetation,
                    "Land_use": sample.Land_use,
                    "Agricultural_land": sample.Agricultural_land,
                    "Ecosystem": sample.Ecosystem,
                    "BaileysEcoregion": sample.BaileysEcoregion,
                    "Grid_Size": sample.Grid_Size,
                    "Soil_depth": sample.Soil_depth,
                    "Transport_refrigeration": sample.Transport_refrigeration,
                    "Drying": sample.Drying,
                    "Date_collected": sample.Date_collected,
                    "DNA_concentration_ng_ul": sample.DNA_concentration_ng_ul,
                    "Elevation": sample.Elevation,
                    "Sample_type": sample.Sample_type,
                    "Sample_or_Control": sample.Sample_or_Control,
                    "IndigenousPartnership": sample.IndigenousPartnership,
                    "Notes": sample.Notes,
                    # DNA regions (comma-separated, e.g. "ITS1,SSU")
                    "dna_regions": (
                        ",".join(sorted(regions)) if regions else None
                    ),
                    # Richness fields (from sequencingAnalysisTypeId = 1)
                    "richness_observed": (
                        richness.observed if richness else None
                    ),
                    "richness_estimator": (
                        richness.estimator if richness else None
                    ),
                    "richness_est_s_e": (
                        richness.est_s_e if richness else None
                    ),
                    "richness_95pct_lower": (
                        richness.x95_percent_lower if richness else None
                    ),
                    "richness_95pct_upper": (
                        richness.x95_percent_upper if richness else None
                    ),
                    "richness_seq_depth": (
                        richness.seq_depth if richness else None
                    ),
                }
            )

    if not data:
        logger.error(
            "No samples with valid coordinates found in the database."
        )
        return None

    uid = uuid.uuid4().hex
    flask_json_path = os.path.join(_FLASK_GEOPANDAS_DIR, f"tmp_{uid}.json")
    flask_gpkg_path = os.path.join(_FLASK_GEOPANDAS_DIR, f"samples_{uid}.gpkg")
    container_json_path = f"{_GEOPANDAS_CONTAINER_DIR}/tmp_{uid}.json"
    container_gpkg_path = f"{_GEOPANDAS_CONTAINER_DIR}/samples_{uid}.gpkg"

    try:
        with open(flask_json_path, "w") as f:
            json.dump(data, f)

        client = docker.from_env()
        container = client.containers.get("spun-geopandas")

        result = container.exec_run(
            [
                "python",
                "create_gpkg.py",
                container_json_path,
                container_gpkg_path,
            ]
        )

        output = result.output.decode()
        logger.info(f"create_gpkg.py output: {output}")

        if result.exit_code != 0:
            logger.error(
                f"Geopandas container error (exit {result.exit_code}): {output}"
            )
            return None

        if not os.path.exists(flask_gpkg_path):
            logger.error(
                "GPKG file was not created by the geopandas container."
            )
            return None

        with open(flask_gpkg_path, "rb") as f:
            buf = io.BytesIO(f.read())
        buf.seek(0)
        return buf

    except Exception as e:
        logger.error(f"Error creating GPKG: {e}", exc_info=True)
        return None

    finally:
        for path in (flask_json_path, flask_gpkg_path):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
