import re


def extract_glomeromycetes_ids(tax_file, output_tax_file):
    glomeromycetes_ids = set()  # To store IDs to be removed
    with open(tax_file, "r") as infile, open(output_tax_file, "w") as outfile:
        for line in infile:
            if re.search(r"glomeromycetes", line, re.IGNORECASE):
                # Extract the ID (assumes ID is the first
                # item in each line, separated by whitespace)
                sequence_id = line.split()[0]
                glomeromycetes_ids.add(sequence_id)
            else:
                # Write lines that don't contain Glomeromycetes
                outfile.write(line)
    return glomeromycetes_ids


def remove_glomeromycetes_sequences(
    fasta_file, output_fasta_file, glomeromycetes_ids
):
    with open(fasta_file, "r") as infile, open(
        output_fasta_file, "w"
    ) as outfile:
        write_block = True
        for line in infile:
            if line.startswith(">"):
                # Check if the sequence ID (first word after ">")
                # is in the Glomeromycetes list
                sequence_id = line.split()[0][1:]  # Remove ">" from the ID
                write_block = sequence_id not in glomeromycetes_ids
            if write_block:
                outfile.write(line)


glomeromycetes_ids = extract_glomeromycetes_ids(
    "lotus2_files/SLV_138.1_SSU.tax", "lotus2_files/SLV_138.1_SSU_NO_AMF.tax"
)

remove_glomeromycetes_sequences(
    "lotus2_files/SLV_138.1_SSU.fasta",
    "lotus2_files/SLV_138.1_SSU_NO_AMF.fasta",
    glomeromycetes_ids,
)
