import subprocess
import re


def run_cutadapt_analysis(
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


def parse_cutadapt_output(log_output):
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
