"""
One-off audit: for every sequencing upload, compares the sequencing
platform declared in the database against what the FASTQ files on disk
actually look like (read from each file's own header -- see
helpers/platform_detection.py). Read-only: makes no changes to the
database or to any files.

Some projects are known to legitimately combine more than one sequencing
platform (e.g. projects 6 and 47) -- a "mismatch" or "mixed" result here is
just a factual report of what the files look like, not necessarily an
error; it's on the reader to know which projects that applies to.

Usage (from the repository root):
    docker-compose run --rm flask python scripts/audit_sequencing_platforms.py
    docker-compose run --rm flask python scripts/audit_sequencing_platforms.py <upload_id> [<upload_id> ...]
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.dbm import session_scope  # noqa: E402
from helpers.platform_detection import audit_upload_platform  # noqa: E402
from models.db_model import SequencingUploadsTable  # noqa: E402


def get_upload_ids(only_ids=None):
    with session_scope() as session:
        query = session.query(SequencingUploadsTable.id).order_by(
            SequencingUploadsTable.id
        )
        if only_ids:
            query = query.filter(SequencingUploadsTable.id.in_(only_ids))
        return [row[0] for row in query.all()]


def print_report(only_ids=None):
    upload_ids = get_upload_ids(only_ids)

    summary = {
        "all_match": [],
        "mixed": [],
        "no_match": [],
        "indeterminate": [],
        "no_expectation": [],
        "no_files": [],
    }

    for upload_id in upload_ids:
        result = audit_upload_platform(upload_id)
        if result is None:
            continue

        header = (
            f"Upload {upload_id} "
            f"(project '{result['project_id']}', "
            f"folder {result['uploads_folder']})"
        )
        print(f"{header}: {result['verdict']}")

        if result["total_files"] == 0:
            summary["no_files"].append(upload_id)
        elif result["no_expectation"] == result["total_files"]:
            summary["no_expectation"].append(upload_id)
        elif result["indeterminate"] == result["total_files"]:
            summary["indeterminate"].append(upload_id)
        elif result["mismatched"] == 0:
            summary["all_match"].append(upload_id)
        elif result["matched"] == 0:
            summary["no_match"].append(upload_id)
        else:
            summary["mixed"].append(upload_id)

    print("\n=== Summary ===")
    print(
        f"All files match declared platform: {len(summary['all_match'])} "
        f"{summary['all_match']}"
    )
    print(
        f"Mixed (some match, some don't):     {len(summary['mixed'])} "
        f"{summary['mixed']}"
    )
    print(
        f"No files match declared platform:   {len(summary['no_match'])} "
        f"{summary['no_match']}"
    )
    print(
        f"Could not determine from files:     {len(summary['indeterminate'])} "
        f"{summary['indeterminate']}"
    )
    print(
        f"Declared platform not checkable:    {len(summary['no_expectation'])} "
        f"{summary['no_expectation']}"
    )
    print(
        f"No FASTQ files found on disk:        {len(summary['no_files'])} "
        f"{summary['no_files']}"
    )


if __name__ == "__main__":
    ids = [int(a) for a in sys.argv[1:]] if len(sys.argv) > 1 else None
    print_report(ids)
