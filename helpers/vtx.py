import pandas as pd
import logging
from pathlib import Path

logger = logging.getLogger("my_app_logger")


def generate_vtx_file(lotus_2_dir, output_dir):
    # 1. Define input/output paths
    base = Path("/app")
    input_file = base / lotus_2_dir.lstrip("/") / "ExtraFiles" / "tax.0.blast"
    output_file = (
        base
        / output_dir.lstrip("/")
        / "SSU_dada2_ASV_VTX_tophit_pident97_qcov98.tsv"
    )

    # 2. Define headers (BLAST outfmt 6 usually doesn't have them)
    headers = [
        "qaccver",
        "saccver",
        "pident",
        "length",
        "mismatch",
        "gapopen",
        "qstart",
        "qend",
        "sstart",
        "send",
        "qlen",
        "evalue",
        "bitscore",
    ]

    # 3. Read the data
    df = pd.read_csv(input_file, sep="\t", names=headers)

    # 4. Calculate Query Coverage (qcov)
    # Formula: (qend - qstart + 1) / qlen
    df["qcov"] = ((df["qend"] - df["qstart"] + 1) / df["qlen"]) * 100

    # 5. Apply Filters
    # - pident >= 97
    # - qcov >= 98 (since we multiplied by 100 above)
    mask = (df["pident"] >= 97) & (df["qcov"] >= 98)
    filtered_df = df[mask].copy()

    # 6. Keep only the first hit for each query (found[$1]++ < 1)
    # BLAST files are usually sorted by bitscore, so 'first' is usually the best hit
    top_hits = filtered_df.drop_duplicates(subset="qaccver", keep="first")

    # 7. Format ONLY the qcov column to 2 decimal places
    # We convert it to a string so to_csv doesn't try to format it again
    formatted_qcov = top_hits["qcov"].map(lambda x: f"{x:.2f}")
    top_hits = top_hits.assign(qcov=formatted_qcov)

    # 8. Select and format columns for output
    # The original columns plus qcov
    output_columns = [
        "qaccver",
        "saccver",
        "pident",
        "length",
        "mismatch",
        "gapopen",
        "qstart",
        "qend",
        "sstart",
        "send",
        "qlen",
        "qcov",
    ]

    top_hits[output_columns].to_csv(output_file, sep="\t", index=False)
