import glob
import gzip
import os
import shutil

from helpers.platform_detection import (
    audit_fastq_files,
    classify_header,
    read_first_fastq_header,
)

FASTQ_FILES_DIR = os.path.join(os.path.dirname(__file__), "fastq_files")


def test_classify_header_illumina_nextseq():
    header = (
        "VH01408:107:AAHKMWHM5:1:1101:52353:1227 1:N:0:GAAGGATTCA+TGAACTTGAC"
    )
    result = classify_header(header)
    assert result["family"] == "illumina"
    assert result["detected_platform"] == "Illumina NextSeq"


def test_classify_header_aviti():
    header = (
        "AV233601:ca_av_0178_20240927_SPUN_B_FS_2x300_Med:2411440970:"
        "1:10801:0244:0071 1:N:0:CTAGATTGCG+CGCCATATCT"
    )
    result = classify_header(header)
    assert result["family"] == "aviti"
    assert result["detected_platform"] == "Element Biosciences AVITI"


def test_classify_header_illumina_miseq():
    header = "M01234:56:000000000-A1B2C:1:1101:15000:1000 1:N:0:1"
    result = classify_header(header)
    assert result["family"] == "illumina"
    assert result["detected_platform"] == "Illumina MiSeq"


def test_classify_header_unknown_model_still_counted_as_illumina():
    # Casava-shaped header, but an instrument prefix not in our table.
    header = "ZZ99999:1:FLOWCELL123:1:1101:1000:2000 1:N:0:AAAA"
    result = classify_header(header)
    assert result["family"] == "illumina"
    assert result["detected_platform"] == "Illumina (other)"


def test_classify_header_nanopore():
    header = (
        "a1b2c3d4-0000-1111-2222-333344445555 runid=deadbeef "
        "read=123 ch=456 start_time=2026-01-01T00:00:00Z"
    )
    result = classify_header(header)
    assert result["family"] == "nanopore"
    assert result["detected_platform"] == "Nanopore (ONT, any)"


def test_classify_header_pacbio_ccs():
    header = "m64011_201218_000000/12345/ccs"
    result = classify_header(header)
    assert result["family"] == "pacbio"
    assert result["detected_platform"] == "PacBio (other)"


def test_classify_header_garbage_is_unknown():
    result = classify_header("not a recognisable read header")
    assert result["family"] == "unknown"
    assert result["detected_platform"] is None


def test_classify_header_none_is_unknown():
    result = classify_header(None)
    assert result["family"] == "unknown"


def test_audit_fastq_files_all_match_real_illumina_fixtures():
    fastq_paths = sorted(
        glob.glob(os.path.join(FASTQ_FILES_DIR, "*.fastq.gz"))
    )
    assert fastq_paths  # sanity: fixture files exist

    result = audit_fastq_files(fastq_paths, "Illumina NextSeq")

    assert result["total_files"] == len(fastq_paths)
    assert result["matched"] == len(fastq_paths)
    assert result["mismatched"] == 0
    assert "All" in result["verdict"]
    assert "match the declared platform" in result["verdict"]


def test_audit_fastq_files_mismatch_against_wrong_declared_platform():
    fastq_paths = sorted(
        glob.glob(os.path.join(FASTQ_FILES_DIR, "*.fastq.gz"))
    )

    result = audit_fastq_files(fastq_paths, "Element Biosciences AVITI")

    assert result["matched"] == 0
    assert result["mismatched"] == len(fastq_paths)
    assert "None of the" in result["verdict"]
    assert "Illumina NextSeq" in result["detected_breakdown"]


def test_audit_fastq_files_declared_other_has_no_expectation():
    fastq_paths = sorted(
        glob.glob(os.path.join(FASTQ_FILES_DIR, "*.fastq.gz"))
    )[:2]

    result = audit_fastq_files(fastq_paths, "Other")

    assert result["no_expectation"] == len(fastq_paths)
    assert result["matched"] == 0
    assert result["mismatched"] == 0
    assert "has no reference signature" in result["verdict"]


def test_audit_fastq_files_no_files_found():
    result = audit_fastq_files([], "Illumina NextSeq")

    assert result["total_files"] == 0
    assert result["verdict"] == "No FASTQ files found on disk for this upload."


def test_read_first_fastq_header_detects_gzip_despite_wrong_extension(
    tmp_path,
):
    # A real .fastq.gz fixture, copied under a plain ".fastq" name -- the
    # content is still gzip-compressed, only the extension lies.
    real_gz = sorted(glob.glob(os.path.join(FASTQ_FILES_DIR, "*.fastq.gz")))[0]
    mislabeled = tmp_path / "mislabeled.fastq"
    shutil.copyfile(real_gz, mislabeled)

    header = read_first_fastq_header(str(mislabeled))

    with gzip.open(real_gz, "rt") as f:
        expected_header = f.readline().strip()[1:]

    assert header == expected_header


def test_read_first_fastq_header_detects_plain_text_despite_gz_extension(
    tmp_path,
):
    # A plain-text FASTQ saved under a ".fastq.gz" name -- not actually
    # compressed.
    plain_header = "@FAKE:1:FLOWCELL:1:1101:1000:2000 1:N:0:AAAA"
    mislabeled = tmp_path / "not_really_gzipped.fastq.gz"
    mislabeled.write_text(f"{plain_header}\n+\nACGT\n+\nFFFF\n")

    header = read_first_fastq_header(str(mislabeled))

    assert header == plain_header[1:]
