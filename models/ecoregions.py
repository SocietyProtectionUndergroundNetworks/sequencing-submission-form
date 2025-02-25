import logging
from sqlalchemy.sql import case, func
from models.db_model import (
    ResolveEcoregionsTable,
    SequencingSamplesTable,
    ExternalSamplingTable,
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

            num_sequencing_samples = func.count(func.distinct(ss.id)).label(
                "num_sequencing_samples"
            )

            num_external_samples_ITS = func.count(
                func.distinct(
                    case((es.dna_region == "ITS", es.id), else_=None)
                )
            ).label("num_external_samples_ITS")

            num_external_samples_SSU = func.count(
                func.distinct(
                    case((es.dna_region == "SSU", es.id), else_=None)
                )
            ).label("num_external_samples_SSU")

            query = (
                session.query(
                    re.ecoregion_name,
                    num_sequencing_samples,
                    num_external_samples_ITS,
                    num_external_samples_SSU,
                )
                .outerjoin(ss, ss.resolve_ecoregion_id == re.id)
                .outerjoin(es, es.resolve_ecoregion_id == re.id)
                .group_by(re.ecoregion_name)
            )

            return query.all()
