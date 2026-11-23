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
    docker-compose run --rm flask python scripts/audit_sequencing_platforms.py --csv /app/my_report.csv
    docker-compose run --rm flask python scripts/audit_sequencing_platforms.py --no-csv
"""

import argparse
import csv
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.dbm import session_scope  # noqa: E402
from helpers.platform_detection import audit_upload_platform  # noqa: E402
from models.db_model import SequencingUploadsTable  # noqa: E402

DEFAULT_CSV_PATH = "platform_audit_report.csv"

CSV_FIELDNAMES = [
    "upload_id",
    "project_id",
    "uploads_folder",
    "declared_platform",
    "category",
    "total_files",
    "matched",
    "mismatched",
    "indeterminate",
    "no_expectation",
    "detected_platforms",
    "verdict",
]

CATEGORY_LABELS = {
    "all_match": "All files match declared platform",
    "mixed": "Mixed (some match, some don't)",
    "no_match": "No files match declared platform",
    "indeterminate": "Could not determine from files",
    "no_expectation": "Declared platform not checkable",
    "no_files": "No FASTQ files found on disk",
}


def get_upload_ids(only_ids=None):
    with session_scope() as session:
        query = session.query(SequencingUploadsTable.id).order_by(
            SequencingUploadsTable.id
        )
        if only_ids:
            query = query.filter(SequencingUploadsTable.id.in_(only_ids))
        return [row[0] for row in query.all()]


def categorize(result):
    if result["total_files"] == 0:
        return "no_files"
    if result["no_expectation"] == result["total_files"]:
        return "no_expectation"
    if result["indeterminate"] == result["total_files"]:
        return "indeterminate"
    if result["mismatched"] == 0:
        return "all_match"
    if result["matched"] == 0:
        return "no_match"
    return "mixed"


def format_detected_platforms(detected_breakdown):
    by_count_desc = sorted(
        detected_breakdown.items(), key=lambda item: item[1], reverse=True
    )
    return "; ".join(f"{platform} ({n})" for platform, n in by_count_desc)


def build_rows(upload_ids):
    """
    Runs the audit for each upload id and returns (rows, summary):
      - rows: one dict per upload, in CSV_FIELDNAMES order, ready to feed
        straight to csv.DictWriter.
      - summary: {category: [upload_id, ...]}, for the console report.
    """
    rows = []
    summary = {category: [] for category in CATEGORY_LABELS}

    for upload_id in upload_ids:
        result = audit_upload_platform(upload_id)
        if result is None:
            continue

        category = categorize(result)
        summary[category].append(upload_id)

        rows.append(
            {
                "upload_id": upload_id,
                "project_id": result["project_id"],
                "uploads_folder": result["uploads_folder"],
                "declared_platform": result["declared_platform"] or "",
                "category": category,
                "total_files": result["total_files"],
                "matched": result["matched"],
                "mismatched": result["mismatched"],
                "indeterminate": result["indeterminate"],
                "no_expectation": result["no_expectation"],
                "detected_platforms": format_detected_platforms(
                    result["detected_breakdown"]
                ),
                "verdict": result["verdict"],
            }
        )

    return rows, summary


def print_report(rows, summary):
    for row in rows:
        header = (
            f"Upload {row['upload_id']} "
            f"(project '{row['project_id']}', "
            f"folder {row['uploads_folder']})"
        )
        print(f"{header}: {row['verdict']}")

    print("\n=== Summary ===")
    for category, label in CATEGORY_LABELS.items():
        ids = summary[category]
        print(f"{label}: {len(ids)} {ids}")


def write_csv(rows, csv_path):
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV report written to {csv_path} ({len(rows)} row(s)).")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Audit sequencing uploads: declared platform vs. what the "
            "FASTQ files on disk actually look like. Read-only."
        )
    )
    parser.add_argument(
        "upload_ids",
        nargs="*",
        type=int,
        help="Specific upload IDs to check (default: every upload).",
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        default=DEFAULT_CSV_PATH,
        help=(
            "Path to write the CSV report to, one row per upload "
            f"(default: {DEFAULT_CSV_PATH})."
        ),
    )
    parser.add_argument(
        "--no-csv",
        dest="write_csv_file",
        action="store_false",
        help="Skip writing the CSV report; only print to the console.",
    )
    args = parser.parse_args()

    upload_ids = get_upload_ids(args.upload_ids or None)
    rows, summary = build_rows(upload_ids)

    print_report(rows, summary)

    if args.write_csv_file:
        write_csv(rows, args.csv_path)


if __name__ == "__main__":
    main()
