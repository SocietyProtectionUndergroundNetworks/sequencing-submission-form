import sys
import os


def split_unite_fasta(input_fasta_file, output_fasta_file, output_tax_file):
    """
    Splits a UNITE FASTA file (with embedded taxonomy) into
    a sequence-only FASTA file and a separate taxonomy file.

    Args:
        input_fasta_file (str): Path to the input UNITE FASTA file.
        output_fasta_file (str): Path for the output sequence FASTA file.
        output_tax_file (str): Path for the output taxonomy file.
    """

    # Check if input file exists
    if not os.path.exists(input_fasta_file):
        print(f"Error: Input file '{input_fasta_file}' not found.")
        sys.exit(1)

    try:
        with open(input_fasta_file, "r") as infile, open(
            output_fasta_file, "w"
        ) as seq_outfile, open(output_tax_file, "w") as tax_outfile:

            for line in infile:
                if line.startswith(">"):
                    # This is a header line

                    # Find the last '|' to separate ID from taxonomy
                    # We are looking for the pattern like '|k__Fungi;...'
                    last_pipe_index = line.rfind("|")

                    # Ensure there's a pipe and the part after it starts with k__
                    if last_pipe_index != -1 and line[
                        last_pipe_index + 1 :
                    ].strip().startswith("k__"):
                        header_id_with_gt = line[
                            :last_pipe_index
                        ]  # Includes '>'
                        taxonomy = line[last_pipe_index + 1 :].strip()

                        # Write to the sequence FASTA file (original header without taxonomy)
                        seq_outfile.write(header_id_with_gt + "\n")

                        # Write to the taxonomy file (ID tab taxonomy)
                        tax_outfile.write(
                            header_id_with_gt[1:] + "\t" + taxonomy + "\n"
                        )  # [1:] to remove '>'
                    else:
                        # This case should be rare if the file format is consistent
                        # It means a header line without the expected taxonomy string at the end
                        seq_outfile.write(line)  # Write the full header as is
                        print(
                            f"Warning: Unexpected header format (no 'k__' taxonomy found after last '|'). Full line written to sequence file: {line.strip()}",
                            file=sys.stderr,
                        )
                else:
                    # This is a sequence line, write directly to sequence file
                    seq_outfile.write(line)

        print(f"Successfully separated '{input_fasta_file}' into:")
        print(f"- Sequences: '{output_fasta_file}'")
        print(f"- Taxonomy: '{output_tax_file}'")

    except IOError as e:
        print(f"Error: Could not write to output file. {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Check if the correct number of arguments is provided
    if len(sys.argv) != 4:
        print(
            "Usage: python split_unite_fasta.py <input_fasta_file> <output_fasta_file> <output_tax_file>"
        )
        print(
            "Example: python split_unite_fasta.py unite_v10.fasta unite_v10_seq.fasta unite_v10.tax"
        )
        sys.exit(1)

    # Get arguments from command line
    input_file = sys.argv[1]
    output_seq_file = sys.argv[2]
    output_tax_file = sys.argv[3]

    split_unite_fasta(input_file, output_seq_file, output_tax_file)
