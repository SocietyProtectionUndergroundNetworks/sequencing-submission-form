def remove_amf_taxonomies(input_file, output_file):
    with open(input_file, "r") as infile, open(output_file, "w") as outfile:
        for line in infile:
            # Check if the line contains an AMF ID or AMF-related taxonomy
            if not line.startswith("AMF"):  # Skip lines starting with AMF IDs
                outfile.write(line)


def remove_amf_blocks(input_file, output_file):
    with open(input_file, "r") as infile, open(output_file, "w") as outfile:
        write_block = (
            True  # Flag to determine whether to write lines to output
        )
        for line in infile:
            if line.startswith(">"):  # Detect header lines
                # Check if this block should be skipped
                write_block = not line.startswith(">AMF")
            # Only write lines if we're not in an AMF block
            if write_block:
                outfile.write(line)


remove_amf_blocks(
    "lotus2_files/SLV_138.1_SSU.fasta",
    "lotus2_files/SLV_138.1_SSU_NO_AMF.fasta",
)
remove_amf_taxonomies(
    "lotus2_files/SLV_138.1_SSU.tax", "lotus2_files/SLV_138.1_SSU_NO_AMF.tax"
)
