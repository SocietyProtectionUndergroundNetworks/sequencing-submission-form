import logging
from sqlalchemy.sql import case, func
from models.db_model import (
    ResolveEcoregionsTable,
    SequencingSamplesTable,
    ExternalSamplingTable,
    SequencingSequencerIDsTable,
    SequencingUploadsTable,
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
            su = SequencingUploadsTable

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

            # Samples belonging to Spun Led projects (project id starts
            # with "sl-")
            num_spun_led_samples = func.count(
                func.distinct(
                    case(
                        (su.project_id.ilike("sl-%"), ss.id),
                        else_=None,
                    )
                )
            ).label("num_spun_led_samples")

            # Samples belonging to UEP projects (project id starts
            # with "ue-")
            num_uep_samples = func.count(
                func.distinct(
                    case(
                        (su.project_id.ilike("ue-%"), ss.id),
                        else_=None,
                    )
                )
            ).label("num_uep_samples")

            # Samples belonging to SPUN Third Party programs (project id
            # starts with "tp-")
            num_third_party_samples = func.count(
                func.distinct(
                    case(
                        (su.project_id.ilike("tp-%"), ss.id),
                        else_=None,
                    )
                )
            ).label("num_third_party_samples")

            # Samples belonging to BZ projects (project id starts
            # with "bz-")
            num_bz_samples = func.count(
                func.distinct(
                    case(
                        (su.project_id.ilike("bz-%"), ss.id),
                        else_=None,
                    )
                )
            ).label("num_bz_samples")

            # Query
            query = (
                session.query(
                    re.ecoregion_name,
                    num_sequencing_samples,
                    num_sequencing_samples_ITS,
                    num_sequencing_samples_SSU,
                    num_external_samples_ITS,
                    num_external_samples_SSU,
                    num_spun_led_samples,
                    num_uep_samples,
                    num_third_party_samples,
                    num_bz_samples,
                )
                .outerjoin(ss, ss.resolve_ecoregion_id == re.id)
                .outerjoin(
                    ssi, ssi.sequencingSampleId == ss.id
                )  # Join to Sequencer IDs
                .outerjoin(es, es.resolve_ecoregion_id == re.id)
                .outerjoin(su, su.id == ss.sequencingUploadId)
                .group_by(re.ecoregion_name)
            )

            return query.all()
