#!/bin/bash

# Print all passed arguments to check if they are correct
echo "Arguments passed: $@"

# Check if the correct number of arguments are provided
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 -forward|-reverse FASTQ_FILE"
  exit 1
fi

# Assign command-line arguments to variables
PRIMERS_FILE="metadataconfig/primer_set_regions.json"
PRIMER_TYPE="$1" # Either -forward or -reverse
FASTQ_FILE="$2"

# Remove the leading '-' to match JSON keys
if [ "$PRIMER_TYPE" == "-forward" ]; then
  PRIMER_KEY="Forward Primer"
elif [ "$PRIMER_TYPE" == "-reverse" ]; then
  PRIMER_KEY="Reverse Primer"
else
  echo "Invalid primer type: $PRIMER_TYPE. Use -forward or -reverse."
  exit 1
fi

echo "Primer type: $PRIMER_KEY"
echo "FASTQ file: $FASTQ_FILE"

# Function to extract sequences from JSON file and remove duplicates
extract_unique_sequences() {
  local primer_key="$1"
  jq -r "to_entries | map(select(.value[\"$primer_key\"] != null and .value[\"$primer_key\"] != \"\")) | .[].value[\"$primer_key\"]" "$PRIMERS_FILE" | sort -u
}

# Extract unique primers based on the key
sequences=$(extract_unique_sequences "$PRIMER_KEY")
if [ -z "$sequences" ]; then
  echo "No sequences found for \"$PRIMER_KEY\" in the JSON file."
  exit 1
fi
# echo "Unique sequences extracted: $sequences"

# Loop through each unique primer sequence
while IFS= read -r sequence; do
  # Extract primer names and filter the second part
  primer_names=$(jq -r "to_entries | map(select(.value[\"$PRIMER_KEY\"] == \"$sequence\")) | .[].key" "$PRIMERS_FILE")

  # Get the second part of the primer name (e.g., ITS2 from "ITS1/ITS2")
  primer_name_second_part=$(echo "$primer_names" | awk -F'/' '{print $2}' | head -n 1)

  # Count total occurrences of the sequence in the .fastq.gz file
  total_count=$(zgrep -o "$sequence" "$FASTQ_FILE" | wc -l)

  # Count occurrences of the sequence at the beginning of lines
  beginning_count=$(zgrep -o "^$sequence" "$FASTQ_FILE" | wc -l)

  # Print the results in the desired format: second part of primer name (sequence): total_count (beginning_count)
  echo "$primer_name_second_part ($sequence): Total found $total_count. Beginning of line $beginning_count"
done <<< "$sequences"
