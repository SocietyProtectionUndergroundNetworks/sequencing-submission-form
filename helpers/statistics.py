from helpers.dbm import session_scope
from sqlalchemy import text


def get_cohorts_data():
    # we dont want to break the formating of the SQL:
    # fmt: off
    sql = text("""  # noqa: E501
        SELECT
            b.cohort,
            COUNT(DISTINCT b.id) AS number_of_buckets,
            COUNT(DISTINCT su.id) AS number_of_projects_in_app,
            COUNT(DISTINCT CASE WHEN sa_count.sample_count > 0 THEN su.id END) AS projects_with_samples,
            COUNT(DISTINCT CASE WHEN sa_count.sample_count IS NULL OR sa_count.sample_count = 0 THEN su.id END) AS projects_without_samples,
            COALESCE(SUM(sa_count.sample_count), 0) AS total_samples,
            COUNT(DISTINCT CASE WHEN ssi_count.sequencer_count > 0 THEN su.id END) AS projects_with_sequencer_ids,
            COUNT(DISTINCT CASE WHEN sfu_count.file_count > 0 THEN su.id END) AS projects_with_files_uploaded
        FROM buckets AS b
            LEFT JOIN sequencing_uploads AS su ON su.project_id = b.id
            LEFT JOIN (
                SELECT sequencingUploadId, COUNT(id) AS sample_count
                FROM sequencing_samples
                GROUP BY sequencingUploadId
            ) AS sa_count ON sa_count.sequencingUploadId = su.id
            LEFT JOIN (
                SELECT ss.sequencingUploadId, COUNT(ssi.id) AS sequencer_count
                FROM sequencing_samples AS ss
                JOIN sequencing_sequencer_ids AS ssi ON ss.id = ssi.sequencingSampleId
                GROUP BY ss.sequencingUploadId
            ) AS ssi_count ON ssi_count.sequencingUploadId = su.id
            LEFT JOIN (
                SELECT ss.sequencingUploadId, COUNT(sfu.id) AS file_count
                FROM sequencing_samples AS ss
                JOIN sequencing_sequencer_ids AS ssi ON ss.id = ssi.sequencingSampleId
                JOIN sequencing_files_uploaded AS sfu ON ssi.id = sfu.sequencerId
                GROUP BY ss.sequencingUploadId
            ) AS sfu_count ON sfu_count.sequencingUploadId = su.id
        GROUP BY b.cohort;
    """)
    # fmt: on

    with session_scope() as session:
        result = session.execute(sql)
        rows = result.fetchall()

    # Convert to list of dicts
    columns = result.keys()
    return [dict(zip(columns, row)) for row in rows]
