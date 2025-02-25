import logging
from sqlalchemy.orm import aliased
from sqlalchemy.sql import func
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
    def get_counts(self):
        with session_scope() as session:
            query = (
                session.query(
                    ResolveEcoregionsTable.ecoregion_name,
                    func.count(func.distinct(SequencingSamplesTable.id)).label(
                        "num_sequencing_samples"
                    ),
                    func.count(func.distinct(ExternalSamplingTable.id)).label(
                        "num_external_samples"
                    ),
                )
                .outerjoin(
                    SequencingSamplesTable,
                    SequencingSamplesTable.ResolveEcoregion
                    == ResolveEcoregionsTable.ecoregion_name,
                )
                .outerjoin(
                    ExternalSamplingTable,
                    ExternalSamplingTable.resolve_ecoregion_id
                    == ResolveEcoregionsTable.id,
                )
                .group_by(ResolveEcoregionsTable.ecoregion_name)
            )

            results = query.all()
            return results
