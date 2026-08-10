#!/bin/bash
#
# identify_primers.sh
#
# Purpose: given a FASTQ(.gz) file of unknown origin, figure out which
# known primer set (from primer_set_regions.json) was used to generate it,
# by checking for literal AND reverse-complement primer sequences.
#
# This intentionally does NOT require the user to know in advance whether
# the file uses forward or reverse primers, or in which orientation they
# were sequenced -- that's the whole point of the script.
#
# Paired files: if a mate file can be found next to the one you pass in
# (R1/R2 or _1/_2 naming), it is analyzed automatically alongside it, so
# you only ever need to point this at one of the two files.

# -e          : exit immediately if any command fails
# -u          : treat use of an unset variable as an error
# -o pipefail : a pipeline's exit status is the first non-zero one in it,
#               not just the exit status of the last command
# Together these make the script fail loudly instead of silently limping
# along with bad data (e.g. an empty $seq from a typo'd JSON key).
set -euo pipefail

# Path to the primer lookup table. This JSON is shared with other parts of
# the pipeline (hence the "...Revcomp" fields existing at all), so we treat
# it as read-only reference data here.
PRIMERS_FILE="metadataconfig/primer_set_regions.json"

# ---------------------------------------------------------------------------
# Usage / help text
# ---------------------------------------------------------------------------
# Printed whenever arguments are missing or unrecognized. Everything goes to
# stderr (>&2) so it doesn't pollute stdout if someone pipes/redirects the
# script's actual results.
usage() {
  echo "Usage: $0 FASTQ_FILE [-forward|-reverse|-all] [--mate FILE|--no-mate]" >&2
  echo "  -forward   : only check Forward Primer / Forward Primer Revcomp" >&2
  echo "  -reverse   : only check Reverse Primer / Reverse Primer Revcomp" >&2
  echo "  -all       : check all four fields (default)" >&2
  echo "  --mate FILE: explicitly specify the paired file (skips auto-detection)" >&2
  echo "  --no-mate  : only analyze the single file given, don't look for a pair" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
# The first positional argument is always the FASTQ file. Everything after
# that is optional and can appear in any order, so we parse it with a manual
# while/case loop rather than fixed positions.
[ "$#" -ge 1 ] || usage
FASTQ_FILE="$1"
shift   # consume $1 so the loop below only sees the optional flags

# Defaults: check all four primer fields, no manually-specified mate file,
# and don't skip mate auto-detection unless told to.
MODE="-all"
MATE_FILE=""
NO_MATE=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    -forward|-reverse|-all)
      # One of the three mode flags -- just record it.
      MODE="$1"
      ;;
    --mate)
      # --mate expects a filename as the NEXT argument, so shift once more
      # to consume that value too.
      shift
      [ "$#" -ge 1 ] || usage
      MATE_FILE="$1"
      ;;
    --no-mate)
      NO_MATE=1
      ;;
    *)
      # Anything else is an argument we don't recognize.
      usage
      ;;
  esac
  shift
done

# ---------------------------------------------------------------------------
# Sanity checks on inputs before doing any real work
# ---------------------------------------------------------------------------
[ -f "$FASTQ_FILE" ] || { echo "File not found: $FASTQ_FILE" >&2; exit 1; }
[ -f "$PRIMERS_FILE" ] || { echo "Primers file not found: $PRIMERS_FILE" >&2; exit 1; }

# Translate the chosen mode into the actual JSON field names we'll look up
# for each primer set entry. -all covers both orientations of both primers,
# which matters because we don't know in advance which orientation the
# sequencer produced (see header comment).
case "$MODE" in
  -forward) FIELDS=("Forward Primer" "Forward Primer Revcomp") ;;
  -reverse) FIELDS=("Reverse Primer" "Reverse Primer Revcomp") ;;
  -all)     FIELDS=("Forward Primer" "Forward Primer Revcomp" "Reverse Primer" "Reverse Primer Revcomp") ;;
esac

# ---------------------------------------------------------------------------
# Mate-file auto-detection
# ---------------------------------------------------------------------------
# Given one file of a pair, try to guess the filename of its mate and check
# whether that file actually exists on disk. We try two naming conventions,
# in order:
#   1. Illumina-style: the token "R1" or "R2" appears somewhere in the name,
#      bounded by _ . or - (or the start/end of the string) so we don't
#      accidentally match "R1" inside an unrelated word.
#      e.g. RB20_AMF_S567_L001_R1_001.fastq.gz -> ..._R2_001.fastq.gz
#   2. Simple suffix style: a trailing _1 or _2 right before the
#      .fastq/.fq (optionally .gz) extension.
#      e.g. P_yunga_20_SSU_2.fastq.gz -> P_yunga_20_SSU_1.fastq.gz
#
# Returns (via echo + exit code 0) the path to the mate file if found, or
# exits 1 if none of the candidate names exist on disk.
find_mate() {
  local file="$1" dir base c
  dir=$(dirname "$file")
  base=$(basename "$file")
  local candidates=()

  # --- Illumina R1 <-> R2 substitution ---
  # sed only performs the substitution if the R1/R2 token (with boundary)
  # is actually present; otherwise $c comes back identical to $base, which
  # we detect below and skip.
  c=$(echo "$base" | sed -E 's/(^|[_.-])R1([_.-]|$)/\1R2\2/')
  [ "$c" != "$base" ] && candidates+=("$c")
  c=$(echo "$base" | sed -E 's/(^|[_.-])R2([_.-]|$)/\1R1\2/')
  [ "$c" != "$base" ] && candidates+=("$c")

  # --- Trailing _1 <-> _2 substitution ---
  # Anchored to the end of the filename (immediately before the extension)
  # so this doesn't misfire on a "_1" or "_2" that appears earlier in the
  # sample name.
  c=$(echo "$base" | sed -E 's/_1(\.fastq(\.gz)?|\.fq(\.gz)?)$/_2\1/')
  [ "$c" != "$base" ] && candidates+=("$c")
  c=$(echo "$base" | sed -E 's/_2(\.fastq(\.gz)?|\.fq(\.gz)?)$/_1\1/')
  [ "$c" != "$base" ] && candidates+=("$c")

  # Check each candidate name against the filesystem (same directory as the
  # original file) and return the first one that actually exists.
  local cand
  for cand in "${candidates[@]:-}"; do
    [ -z "$cand" ] && continue
    if [ -f "$dir/$cand" ]; then
      echo "$dir/$cand"
      return 0
    fi
  done
  return 1   # no candidate name matched an existing file
}

# Build the list of files to actually analyze: always the file the user
# passed in, plus (unless disabled) its detected or manually-specified mate.
FILES=("$FASTQ_FILE")
if [ "$NO_MATE" -eq 1 ]; then
  : # user explicitly opted out via --no-mate; analyze $FASTQ_FILE alone
elif [ -n "$MATE_FILE" ]; then
  # User gave us the mate explicitly -- trust it, just confirm it exists.
  [ -f "$MATE_FILE" ] || { echo "Mate file not found: $MATE_FILE" >&2; exit 1; }
  FILES+=("$MATE_FILE")
else
  # Try auto-detection. If nothing is found, don't fail the whole run --
  # just warn and continue analyzing the single file, same as before this
  # feature existed.
  if MATE_FOUND=$(find_mate "$FASTQ_FILE"); then
    FILES+=("$MATE_FOUND")
  else
    echo "Note: no paired file auto-detected next to $FASTQ_FILE -- analyzing it alone." >&2
    echo "      (use --mate FILE to specify one manually)" >&2
    echo >&2
  fi
fi

# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------
# RESULTS accumulates one tab-separated line per (file, primer set, field)
# combination that had at least one match, across all files in $FILES.
# We build it up first and format/sort it for display afterwards, rather
# than printing as we go, so we can sort by match count and show per-file
# summaries at the end.
RESULTS="$(mktemp)"
trap 'rm -f "$RESULTS"' EXIT   # clean up the temp file no matter how we exit

for f in "${FILES[@]}"; do
  # Pick the right way to read the file depending on whether it's gzipped.
  case "$f" in
    *.gz) READ_CMD=(zcat "$f") ;;
    *)    READ_CMD=(cat "$f") ;;
  esac

  # Extract ONLY the sequence lines of the FASTQ file. A FASTQ record is
  # always 4 lines: @header / sequence / + / quality-scores. Using
  # `awk 'NR % 4 == 2'` grabs just line 2 of every record (the sequence),
  # so grep below can never accidentally match a header or quality line --
  # which was the bug in the original script's "^$sequence" check.
  SEQ_LINES="$(mktemp)"
  "${READ_CMD[@]}" | awk 'NR % 4 == 2' > "$SEQ_LINES"

  total_reads=$(wc -l < "$SEQ_LINES")
  if [ "$total_reads" -eq 0 ]; then
    echo "No sequence lines found in $f -- is this a valid FASTQ file?" >&2
    rm -f "$SEQ_LINES"
    continue   # skip to the next file in $FILES rather than aborting entirely
  fi

  # Walk every primer set entry in the JSON (e.g. "ITS3/ITS4", "WANDA/AML2")
  # along with its Region, one per line as tab-separated values via jq.
  while IFS=$'\t' read -r name region; do
    # For each entry, check every field we care about based on -forward /
    # -reverse / -all (literal and/or revcomp sequences).
    for field in "${FIELDS[@]}"; do
      # Look up the actual sequence string for this primer set + field.
      # "// empty" makes jq return nothing (not "null") if the field is
      # missing, which the [ -z "$seq" ] check below skips over cleanly.
      seq=$(jq -r --arg n "$name" --arg f "$field" '.[$n][$f] // empty' "$PRIMERS_FILE")
      [ -z "$seq" ] && continue

      # Total: how many reads contain this sequence anywhere.
      # At_start: how many reads have it right at the beginning (i.e. the
      # primer hasn't been trimmed off yet). `|| true` prevents `set -e`
      # from killing the script when grep finds zero matches (grep exits
      # non-zero in that case, which is not an error condition for us).
      total=$(grep -c -- "$seq" "$SEQ_LINES" || true)
      at_start=$(grep -c -- "^$seq" "$SEQ_LINES" || true)

      # Only record a result row if we actually found something -- this
      # keeps the final table free of primer sets/fields with zero hits.
      if [ "$total" -gt 0 ]; then
        pct=$(awk -v t="$total" -v r="$total_reads" 'BEGIN{printf "%.1f", (t/r)*100}')
        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
          "$(basename "$f")" "$name" "$region" "$field" "$seq" "$total" "$at_start" "$pct" >> "$RESULTS"
      fi
    done
  done < <(jq -r 'to_entries[] | [.key, (.value.Region // "NA")] | @tsv' "$PRIMERS_FILE")

  echo "File: $f ($total_reads reads)" >&2
  rm -f "$SEQ_LINES"
done
echo >&2

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
# If nothing matched in any file, say so plainly instead of printing an
# empty/confusing table.
if [ ! -s "$RESULTS" ]; then
  echo "No known primer sequences (or their reverse complements) were found."
  echo "The primer set may not be in $PRIMERS_FILE, or primers may already be trimmed"
  echo "and heavily degraded/mismatched."
  exit 0
fi

# Print the full results table: header row, then all result rows sorted
# first by filename (-k1,1) and, within each file, by match count
# descending (-k6,6nr) so the strongest hit for each file appears first.
# The final awk just pads columns for readability (a lightweight stand-in
# for `column -t`, which isn't guaranteed to be installed everywhere).
{
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "File" "Primer_Set" "Region" "Field" "Sequence" "Total" "At_Start" "Pct"
  sort -t $'\t' -k1,1 -k6,6nr "$RESULTS"
} | awk -F'\t' '{printf "%-38s %-12s %-8s %-24s %-24s %-8s %-10s %s\n", $1, $2, $3, $4, $5, $6, $7, $8"%"}'

echo
# For each file we analyzed, pull out its single strongest match (highest
# Total count) and print a one-line summary. This is the "so what" line --
# e.g. seeing "R1 -> Forward Primer" and "R2 -> Reverse Primer" together
# tells you which primer set was used AND which file is which read, without
# you having to read the whole table above.
for f in "${FILES[@]}"; do
  fname=$(basename "$f")
  best=$(awk -F'\t' -v fn="$fname" '$1==fn' "$RESULTS" | sort -t $'\t' -k6,6nr | head -n 1)
  if [ -n "$best" ]; then
    b_name=$(echo "$best" | cut -f2)
    b_field=$(echo "$best" | cut -f4)
    b_pct=$(echo "$best" | cut -f8)
    echo "$fname -- best match: $b_name ($b_field), ${b_pct}% of reads"
  fi
done