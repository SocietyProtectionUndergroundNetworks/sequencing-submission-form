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
  # Count occurrences of the sequence in the .fastq.gz file
  count=$(zgrep -o "$sequence" "$FASTQ_FILE" | wc -l)
  
  # Print the result in the format: sequence: count
  echo "$sequence: $count"
done < "$PRIMERS_FILE"