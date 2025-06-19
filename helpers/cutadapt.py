import subprocess
import re
import logging

logger = logging.getLogger("my_app_logger")


def detect_single_read_primers(
    file_1_path, file_2_path, forward_primer_seq, reverse_primer_seq
):
    cmd = [
        "cutadapt",
        "-j 3",
        "--discard-untrimmed",
        "-g",
        f"^{forward_primer_seq}",
        "-G",
        f"^{reverse_primer_seq}",
        file_1_path,
        file_2_path,
        "-o",
        "/dev/null",
        "-p",
        "/dev/null",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )

        return result.stdout

    except subprocess.CalledProcessError as e:
        # You can log or re-raise with more info
        raise RuntimeError(f"Cutadapt failed: {e.stderr}") from e


def parse_detect_single_read_primers_output(log_output):
    read1_match = re.search(r"Read 1 with adapter:\s+([\d,]+)", log_output)
    read2_match = re.search(r"Read 2 with adapter:\s+([\d,]+)", log_output)
    pairs_written_match = re.search(
        r"Pairs written \(passing filters\):\s+([\d,]+)", log_output
    )

    read1 = int(read1_match.group(1).replace(",", "")) if read1_match else None
    read2 = int(read2_match.group(1).replace(",", "")) if read2_match else None
    pairs_written = (
        int(pairs_written_match.group(1).replace(",", ""))
        if pairs_written_match
        else None
    )

    return {
        "read1_with_adapter": read1,
        "read2_with_adapter": read2,
        "pairs_written": pairs_written,
    }


def detect_merged_read_primers(
    file_1_path, file_2_path, forward_primer_seq, reverse_primer_seq
):
    vsearch_cmd = [
        "vsearch",
        "--fastq_allowmergestagger",
        "--fastq_qmax",
        "45",
        "--fasta_width",
        "0",
        "--fastq_mergepairs",
        file_1_path,
        "--reverse",
        file_2_path,
        "--fastqout",
        "-",
    ]

    cutadapt_cmd = [
        "cutadapt",
        "-j",
        "4",
        "--discard-untrimmed",
        "-g",
        f"^{forward_primer_seq}...{reverse_primer_seq}$",
        "-",
    ]

    try:
        # Launch vsearch
        vsearch_proc = subprocess.Popen(
            vsearch_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # Pipe vsearch -> cutadapt, discard cutadapt stdout
        cutadapt_proc = subprocess.run(
            cutadapt_cmd,
            stdin=vsearch_proc.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=True,
        )

        # Close vsearch stdout to allow vsearch
        # to receive SIGPIPE if cutadapt exits
        vsearch_proc.stdout.close()
        vsearch_proc.wait()

        return cutadapt_proc.stderr.decode()

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Cutadapt failed: {e.stderr.decode()}") from e


def parse_detect_merged_read_primers_output(log_output):
    reads_match = re.search(
        r"Reads written \(passing filters\):\s+([\d,]+)", log_output
    )

    reads = int(reads_match.group(1).replace(",", "")) if reads_match else None

    return reads


def find_forward_reverse_files(filename1, filename2):
    """
    Given two filenames, return them as forward and reverse files
    if they differ by only one character (e.g., R1 vs R2 or 1 vs 2).
    Return (forward, reverse), or (None, None) if no valid match.
    """
    if len(filename1) != len(filename2):
        return None, None

    diffs = []
    for i in range(len(filename1)):
        if filename1[i] != filename2[i]:
            diffs.append(i)

    if len(diffs) != 1:
        return None, None

    diff_index = diffs[0]
    char1 = filename1[diff_index].upper()
    char2 = filename2[diff_index].upper()

    if (char1 in {"1", "R"} and char2 in {"2"}) or (
        char1 == "R" and char2 == "F"
    ):
        return filename1, filename2  # filename1 is forward
    elif (char2 in {"1", "R"} and char1 in {"2"}) or (
        char2 == "R" and char1 == "F"
    ):
        return filename2, filename1  # filename2 is forward
    else:
        return None, None
