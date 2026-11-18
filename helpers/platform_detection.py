"""
Best-effort detection of the sequencing platform that actually produced a
set of FASTQ files, read from each file's own read header rather than from
whatever a user declared at upload time (the `Sequencing_platform` field).

This is intentionally conservative: if a header doesn't match a known
signature we report "unknown" rather than guessing, since a false match is
worse than an honest "can't tell".
"""

import glob
import gzip
import logging
import os
import re
from collections import Counter

logger = logging.getLogger("my_app_logger")

# Maps the exact strings used in metadataconfig/sequencing_platform.json
# (the dropdown users pick from) to the broad "family" our detection can
# recognise. `None` means we have no way to validate that declared value
# against file contents (e.g. "Other", or a project that is a legitimate
# mix of platforms and was declared as such).
DECLARED_PLATFORM_FAMILY = {
    "Illumina NextSeq": "illumina",
    "Illumina MiSeq": "illumina",
    "Illumina NovaSeq": "illumina",
    "Illumina (other)": "illumina",
    "PacBio Sequel": "pacbio",
    "PacBio (other)": "pacbio",
    "Element Biosciences AVITI": "aviti",
    "ION Torrent": None,  # no reliable header signature to check against
    "Nanopore (ONT, any)": "nanopore",
    "Other": None,
}

# Illumina instrument-ID prefixes, longest/most specific first.
#
# The header *field layout* below (_CASAVA_RE) is Illumina's own
# documented format:
#   https://support.illumina.com/help/BaseSpace_Sequence_Hub_OLH_009008_2/Source/Informatics/BS/FileFormat_FASTQ-files_swBS.htm
# but Illumina does not publish a table mapping instrument-ID prefixes to
# specific sequencer models. The prefix -> model mapping here is
# community-compiled, from:
#   https://www.biostars.org/p/198143/#9588830
#   https://www.biostars.org/p/288365
# Treat it as unofficial and incomplete: instrument IDs can be
# reconfigured by a site admin, so this is a strong hint, not a guarantee.
_ILLUMINA_INSTRUMENT_PREFIXES = [
    ("HWI-M", "Illumina MiSeq"),
    ("HWI-C", "Illumina HiSeq"),
    ("HWI-D", "Illumina HiSeq"),
    ("HWI-K", "Illumina HiSeq"),
    ("LH", "Illumina NovaSeq"),  # NovaSeq X
    ("VH", "Illumina NextSeq"),  # NextSeq 1000/2000
    ("NB", "Illumina NextSeq"),  # NextSeq 500/550
    ("NS", "Illumina NextSeq"),  # NextSeq 500/550
    ("FS", "Illumina iSeq"),
    ("A0", "Illumina NovaSeq"),
    ("M0", "Illumina MiSeq"),
    ("M1", "Illumina MiSeq"),
    ("M2", "Illumina MiSeq"),
    ("D0", "Illumina HiSeq"),
    ("C0", "Illumina HiSeq"),
    ("K0", "Illumina HiSeq"),
    ("J0", "Illumina HiSeq"),
]

# Casava-style header shared by Illumina and Illumina-compatible platforms:
# instrument:run:flowcell:lane:tile:x:y[ read:filtered:control:index]
# Source (Illumina's own FASTQ file-format reference):
#   https://support.illumina.com/help/BaseSpace_Sequence_Hub_OLH_009008_2/Source/Informatics/BS/FileFormat_FASTQ-files_swBS.htm
_CASAVA_RE = re.compile(
    r"^(?P<instrument>[^: ]+):[^: ]+:[^: ]+:\d+:\d+:\d+:\d+"
    r"(?:\s+\d+:[YN]:\d+:\S*)?$"
)

# Element Biosciences AVITI read headers reuse the same Casava-shaped
# layout above, with an "AV<digits>" instrument ID -- confirmed both
# against real AVITI output already in this app's data (upload 10,
# instrument AV233601) and against Element's own Bases2Fastq docs:
#   https://docs.elembio.io/docs/bases2fastq/outputs/
#   https://docs.elembio.io/docs/bases2fastq/troubleshooting/
_AVITI_INSTRUMENT_RE = re.compile(r"^AV\d+$")

# Oxford Nanopore basecaller (Guppy/Dorado/MinKNOW) FASTQ headers always
# carry a "runid=" tag. Source (ONT's own output-specification docs):
#   https://software-docs.nanoporetech.com/output-specifications/latest/read_formats/fastq/
_NANOPORE_RE = re.compile(r"runid=")

# PacBio CCS/HiFi read names are "{movieName}/{holeNumber}/ccs"; subreads
# use "{movieName}/{holeNumber}/{qStart}_{qEnd}". Source (PacBio's own BAM
# format specification -- FASTQ read names follow the same QNAME scheme):
#   https://pacbiofileformats.readthedocs.io/en/13.0/BAM.html
_PACBIO_RE = re.compile(r"^\S+/\d+/(ccs|\d+_\d+)$")

FASTQ_GLOB_PATTERNS = ("*.fastq.gz", "*.fq.gz", "*.fastq", "*.fq")

_GZIP_MAGIC = b"\x1f\x8b"


def _is_gzip_file(path):
    """
    Checks the actual gzip magic number rather than trusting the file
    extension -- a ".fastq.gz" that was transferred/renamed incorrectly
    and isn't really gzipped (or vice versa) would otherwise raise or
    silently decode garbage.
    """
    try:
        with open(path, "rb") as f:
            return f.read(2) == _GZIP_MAGIC
    except OSError:
        return False


def read_first_fastq_header(fastq_path):
    """
    Reads just the first read header from a (optionally gzipped) FASTQ
    file, without loading the whole file into memory. Returns the header
    text with the leading '@' stripped, or None if it couldn't be read.
    """
    opener = gzip.open if _is_gzip_file(fastq_path) else open
    try:
        with opener(fastq_path, "rt", errors="ignore") as f:
            line = f.readline().strip()
    except (OSError, gzip.BadGzipFile) as e:
        logger.warning(f"Could not read header from {fastq_path}: {e}")
        return None

    if not line.startswith("@"):
        return None
    return line[1:]


def classify_header(header):
    """
    Classifies a single FASTQ read header into a platform family. See the
    comments above each regex/table at the top of this module for the
    source behind each platform's signature.

    Returns a dict with:
      - family: "illumina", "aviti", "nanopore", "pacbio", or "unknown"
      - detected_platform: a specific label where we can tell (matching the
        dropdown values where possible), else None
      - signature: a short string explaining what we matched on, for
        display to a human reviewer
    """
    if not header:
        return {
            "family": "unknown",
            "detected_platform": None,
            "signature": None,
        }

    if _NANOPORE_RE.search(header):
        return {
            "family": "nanopore",
            "detected_platform": "Nanopore (ONT, any)",
            "signature": "header contains 'runid='",
        }

    if _PACBIO_RE.match(header):
        return {
            "family": "pacbio",
            "detected_platform": "PacBio (other)",
            "signature": f"PacBio-style read name ({header})",
        }

    match = _CASAVA_RE.match(header)
    if match:
        instrument = match.group("instrument")

        if _AVITI_INSTRUMENT_RE.match(instrument):
            return {
                "family": "aviti",
                "detected_platform": "Element Biosciences AVITI",
                "signature": f"instrument ID {instrument}",
            }

        for prefix, platform in _ILLUMINA_INSTRUMENT_PREFIXES:
            if instrument.startswith(prefix):
                return {
                    "family": "illumina",
                    "detected_platform": platform,
                    "signature": f"instrument ID {instrument}",
                }

        # Casava-shaped header but an instrument prefix we don't recognise:
        # still confidently Illumina (or an Illumina-compatible clone), just
        # not a specific model we have in our table.
        return {
            "family": "illumina",
            "detected_platform": "Illumina (other)",
            "signature": f"instrument ID {instrument} (unrecognised model)",
        }

    return {"family": "unknown", "detected_platform": None, "signature": None}


def list_fastq_files(uploads_folder):
    base = os.path.join("seq_processed", uploads_folder)
    files = []
    for pattern in FASTQ_GLOB_PATTERNS:
        files.extend(glob.glob(os.path.join(base, pattern)))
    return sorted(files)


def _build_verdict(
    declared_platform, declared_family, total, counts, breakdown
):
    def breakdown_text():
        parts = [
            f"{platform} ({n} file{'s' if n != 1 else ''})"
            for platform, n in breakdown.most_common()
        ]
        return ", ".join(parts)

    if total == 0:
        return "No FASTQ files found on disk for this upload."

    match = counts.get("match", 0)
    mismatch = counts.get("mismatch", 0)
    indeterminate = counts.get("indeterminate", 0)

    if declared_family is None:
        label = declared_platform or "(not set)"
        if indeterminate == total:
            return (
                f"Declared platform is '{label}', and none of the {total} "
                "file(s) had a recognisable platform signature."
            )
        return (
            f"Declared platform is '{label}', which this check has no "
            f"reference signature for. Based on the files: {breakdown_text()}."
        )

    if indeterminate == total:
        return (
            f"Could not determine what platform was used: none of the "
            f"{total} file(s) had a recognisable signature."
        )

    if mismatch == 0 and indeterminate == 0:
        return f"All {total} file(s) match the declared platform ({declared_platform})."

    if mismatch == 0:
        return (
            f"All {match} file(s) with a recognisable signature match the "
            f"declared platform ({declared_platform}); {indeterminate} "
            "file(s) could not be identified."
        )

    if match == 0:
        return (
            f"None of the {total} file(s) match the declared platform "
            f"({declared_platform}); detected instead: {breakdown_text()}."
        )

    return (
        f"{match} of {total} file(s) match the declared platform "
        f"({declared_platform}); the rest appear to be: {breakdown_text()}."
    )


def audit_fastq_files(fastq_paths, declared_platform):
    """
    Runs the detection over an explicit list of FASTQ file paths and
    compares each against `declared_platform` (one of the
    DECLARED_PLATFORM_FAMILY keys, or any free-form string -- an
    unrecognised one is treated the same as "Other": no expectation).

    Returns a dict describing the per-file results and an overall verdict.
    Does not touch the database.
    """
    declared_platform = (declared_platform or "").strip()
    declared_family = DECLARED_PLATFORM_FAMILY.get(declared_platform)

    file_results = []
    for path in fastq_paths:
        header = read_first_fastq_header(path)
        detection = classify_header(header)

        if declared_family is None:
            status = "no_expectation"
        elif detection["family"] == "unknown":
            status = "indeterminate"
        elif detection["family"] == declared_family:
            status = "match"
        else:
            status = "mismatch"

        file_results.append(
            {
                "filename": os.path.basename(path),
                "signature": detection["signature"],
                "detected_platform": detection["detected_platform"],
                "detected_family": detection["family"],
                "status": status,
            }
        )

    counts = Counter(r["status"] for r in file_results)
    detected_breakdown = Counter(
        r["detected_platform"] or "Unrecognised/unknown" for r in file_results
    )

    verdict = _build_verdict(
        declared_platform,
        declared_family,
        len(file_results),
        counts,
        detected_breakdown,
    )

    return {
        "declared_platform": declared_platform or None,
        "files": file_results,
        "total_files": len(file_results),
        "matched": counts.get("match", 0),
        "mismatched": counts.get("mismatch", 0),
        "indeterminate": counts.get("indeterminate", 0),
        "no_expectation": counts.get("no_expectation", 0),
        "detected_breakdown": dict(detected_breakdown),
        "verdict": verdict,
    }


def audit_upload_platform(process_id):
    """
    Runs the platform audit for one SequencingUpload (by id), reading the
    FASTQ files currently on disk under its uploads_folder. Returns None if
    the upload itself doesn't exist. Does not touch the database.
    """
    # Imported lazily to avoid a circular import
    # (models.sequencing_upload imports helpers.lotus2, which is unrelated
    # to this module but keeps the dependency graph simple either way).
    from models.sequencing_upload import SequencingUpload

    process_data = SequencingUpload.get(process_id)
    if not process_data:
        return None

    uploads_folder = process_data.get("uploads_folder")
    fastq_paths = list_fastq_files(uploads_folder) if uploads_folder else []

    result = audit_fastq_files(
        fastq_paths, process_data.get("Sequencing_platform")
    )
    result["process_id"] = process_id
    result["project_id"] = process_data.get("project_id")
    result["uploads_folder"] = uploads_folder
    return result
