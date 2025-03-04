import logging
from sqlalchemy.sql import case, func
from models.db_model import (
    ResolveEcoregionsTable,
    SequencingSamplesTable,
    ExternalSamplingTable,
    SequencingSequencerIDsTable,
)
from helpers.dbm import session_scope

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")


class Ecoregion:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get_counts(cls):
        with session_scope() as session:
            re = ResolveEcoregionsTable
            ss = SequencingSamplesTable
            es = ExternalSamplingTable
            ssi = SequencingSequencerIDsTable

            # Original total count
            num_sequencing_samples = func.count(func.distinct(ss.id)).label(
                "num_sequencing_samples"
            )

            # Combined ITS (ITS1 + ITS2)
            num_sequencing_samples_ITS = func.count(
                func.distinct(
                    case(
                        (ssi.Region.in_(["ITS1", "ITS2"]), ss.id),
                        else_=None,
                    )
                )
            ).label("num_sequencing_samples_ITS")

            # Count for SSU
            num_sequencing_samples_SSU = func.count(
                func.distinct(
                    case(
                        (ssi.Region == "SSU", ss.id),
                        else_=None,
                    )
                )
            ).label("num_sequencing_samples_SSU")

            # External ITS Samples
            num_external_samples_ITS = func.count(
                func.distinct(
                    case(
                        (es.dna_region == "ITS", es.id),
                        else_=None,
                    )
                )
            ).label("num_external_samples_ITS")

            # External SSU Samples
            num_external_samples_SSU = func.count(
                func.distinct(
                    case(
                        (es.dna_region == "SSU", es.id),
                        else_=None,
                    )
                )
            ).label("num_external_samples_SSU")

            # Query
            query = (
                session.query(
                    re.ecoregion_name,
                    num_sequencing_samples,
                    num_sequencing_samples_ITS,
                    num_sequencing_samples_SSU,
                    num_external_samples_ITS,
                    num_external_samples_SSU,
                )
                .outerjoin(ss, ss.resolve_ecoregion_id == re.id)
                .outerjoin(
                    ssi, ssi.sequencingSampleId == ss.id
                )  # Join to Sequencer IDs
                .outerjoin(es, es.resolve_ecoregion_id == re.id)
                .group_by(re.ecoregion_name)
            )

            return query.all()
