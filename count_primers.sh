#!/bin/bash

# Check if both arguments (primers file and fastq.gz file) are provided
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 primers.txt AM9_1.fastq.gz"
  exit 1
fi

# Assign command-line arguments to variables
PRIMERS_FILE="$1"
FASTQ_FILE="$2"

# Loop through each line in the primers file
while IFS= read -r sequence; do
  # Count total occurrences of the sequence in the .fastq.gz file
  total_count=$(zgrep -o "$sequence" "$FASTQ_FILE" | wc -l)
  
  # Count occurrences of the sequence at the beginning of lines
  beginning_count=$(zgrep -o "^$sequence" "$FASTQ_FILE" | wc -l)
  
  # Print the results in the format: sequence: total_count (beginning_count)
  echo "$sequence: $total_count ($beginning_count)"
done < "$PRIMERS_FILE"
