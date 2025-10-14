#!/usr/bin/env python3

import sys
import os
import re

# Define which lines / patterns we want to extract
PATTERNS = {
    "Reads processed": r"Reads processed:\s*([\d,]+)",
    "Reads reverse-translated": r"([\d,]+) reads reverse-translated",
    "Rejected": r"Rejected:\s*([\d,]+)",
    "Accepted (High qual)": r"Accepted \(High qual\):\s*([\d,]+)",
    "Accepted (Mid qual)": r"Accepted \(Mid qual\):\s*([\d,]+)",
    "Bad Reads recovered": r"Bad Reads recovered with dereplication:\s*([\d,]+)",
    "sequence Length Min/Avg/Max": r"- sequence Length :\s*([\d,]+)/([\d,]+)/([\d,]+)",
    "Quality Min/Avg/Max": r"- Quality :\s*([\d,]+)/([\d,]+)/([\d,]+)",
    "Accum. Error": r"- Accum\. Error\s*([\d,.]+)",
    "Trimmed > avg qual": r"> 35 avg qual_ in 20 bp windows\s*:\s*([\d,]+)",
    "Trimmed > acc errors": r">\s*\(1\) acc. errors, trimmed seqs\s*:\s*([\d,]+)",
    "Rejected < min Seq len": r"< min Sequence length \(300\)\s*:\s*([\d,]+)",
    "Rejected < min Seq len after trimming": r"-after Quality trimming\s*:\s*([\d,]+)",
    "Rejected < avg Quality": r"< avg Quality \(35\)\s*:\s*([\d,]+)",
    "Rejected < window avg Quality": r"< window \(50 nt\) avg\. Quality \(35\)\s*:\s*([\d,]+)",
    "Rejected > max Seq len": r"> max Sequence length \(1000\)\s*:\s*([\d,]+)",
    "Rejected > homo-nt run": r"> \(16\) homo-nt run\s*:\s*([\d,]+)",
    "Rejected > amb Bases": r"> \(2\) amb\. Bases\s*:\s*([\d,]+)",
    "Fwd Primer remaining": r"-With fwd Primer remaining.*:\s*([\d,]+)",
    "Rev Primer remaining": r"-With rev Primer remaining.*:\s*([\d,]+)",
    "Barcode unidentified": r"-Barcode unidentified.*:\s*([\d,]+)",
}


def parse_demulti(log_path):
    if not os.path.exists(log_path):
        print(f"File not found: {log_path}")
        return {}

    with open(log_path, "r") as f:
        lines = f.readlines()

    results = {}
    text = "".join(lines)
    for key, pattern in PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            # Join groups if multiple (e.g., Min/Avg/Max)
            results[key] = tuple(
                (
                    int(g.replace(",", ""))
                    if g.replace(",", "").isdigit()
                    else float(g.replace(",", ""))
                )
                for g in match.groups()
            )
        else:
            results[key] = None
    return results


def compare_results(res1, res2):
    all_keys = sorted(res1.keys())
    print(f"{'Metric':<40} | {'Dir1':>15} | {'Dir2':>15} | Diff?")
    print("-" * 85)
    for key in all_keys:
        v1 = res1[key]
        v2 = res2[key]
        diff = v1 != v2
        print(f"{key:<40} | {str(v1):>15} | {str(v2):>15} | {diff}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compare_demulti.py path/to/dir1 path/to/dir2")
        sys.exit(1)

    dir1 = sys.argv[1]
    dir2 = sys.argv[2]

    log1 = os.path.join(dir1, "LotuSLogS", "demulti.log")
    log2 = os.path.join(dir2, "LotuSLogS", "demulti.log")

    res1 = parse_demulti(log1)
    res2 = parse_demulti(log2)

    compare_results(res1, res2)
