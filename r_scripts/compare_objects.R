#!/usr/bin/env Rscript

# Usage:
# Rscript r_scripts/compare_by_taxonomy_sorted_fixed.R path/to/folder1 path/to/folder2

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) stop("Please provide exactly two folder paths as arguments.")
folder1 <- args[1]; folder2 <- args[2]
file1 <- file.path(folder1, "phyloseq.Rdata")
file2 <- file.path(folder2, "phyloseq.Rdata")
if (!file.exists(file1)) stop(paste("File not found:", file1))
if (!file.exists(file2)) stop(paste("File not found:", file2))

suppressPackageStartupMessages({
  library(phyloseq)
  library(dplyr)
  library(tidyr)
})

load_phyloseq <- function(file) {
  env <- new.env()
  load(file, envir = env)
  for (obj in ls(env)) {
    if (inherits(env[[obj]], "phyloseq")) return(env[[obj]])
  }
  stop(paste("No phyloseq object found in", file))
}

ps1 <- load_phyloseq(file1)
ps2 <- load_phyloseq(file2)

summarize_phyloseq <- function(ps) {
  otu <- otu_table(ps)
  # ensure taxa are rows for easy rowSums
  if (!taxa_are_rows(ps)) otu <- t(otu)
  otu_mat <- as.matrix(otu)
  data.frame(
    OTUs = nrow(otu_mat),
    Samples = ncol(otu_mat),
    TotalReads = sum(otu_mat),
    MeanAbundance = mean(otu_mat),
    stringsAsFactors = FALSE
  )
}

cat("=== Summary Statistics ===\n")
cat("Folder 1:\n"); print(summarize_phyloseq(ps1))
cat("\nFolder 2:\n"); print(summarize_phyloseq(ps2)); cat("\n")

# Build taxstring safely
make_taxstrings <- function(tax_table_obj) {
  if (is.null(tax_table_obj)) return(NULL)
  tax_df <- as.data.frame(as(tax_table_obj, "matrix"), stringsAsFactors = FALSE)
  # replace NA with "NA" so paste works
  tax_df[is.na(tax_df)] <- "NA"
  taxstrings <- apply(tax_df, 1, function(x) paste(x, collapse = ";"))
  return(taxstrings)
}

taxstr1 <- make_taxstrings(tax_table(ps1))
taxstr2 <- make_taxstrings(tax_table(ps2))

if (is.null(taxstr1) || is.null(taxstr2)) {
  stop("One of the phyloseq objects has no tax_table; cannot compare by taxonomy.")
}

# Ensure OTU tables have taxa as rows and compute per-OTU totals
otu_mat1 <- as.matrix(if (taxa_are_rows(ps1)) otu_table(ps1) else t(otu_table(ps1)))
otu_mat2 <- as.matrix(if (taxa_are_rows(ps2)) otu_table(ps2) else t(otu_table(ps2)))

# Confirm rownames of OTU matrices correspond to tax_table rownames / taxa_names
# taxa names from phyloseq:
taxa1_names <- rownames(as.data.frame(as(tax_table(ps1), "matrix")))
taxa2_names <- rownames(as.data.frame(as(tax_table(ps2), "matrix")))

# If they differ, try to use taxa_names(ps) which is canonical
if (is.null(rownames(otu_mat1))) stop("otu_mat1 has no rownames")
if (is.null(rownames(otu_mat2))) stop("otu_mat2 has no rownames")

# Map taxstrings to OTU rows safely using taxa_names
names(taxstr1) <- taxa_names(ps1)
names(taxstr2) <- taxa_names(ps2)

# Build data frames: OTU, TaxString, TotalCount
df1 <- data.frame(
  OTU = rownames(otu_mat1),
  Total = rowSums(otu_mat1),
  stringsAsFactors = FALSE
)
df1$TaxString <- taxstr1[df1$OTU]
# if some OTUs missing mapping, fill with NA
df1$TaxString[is.na(df1$TaxString)] <- "UNKNOWN_TAX"

df2 <- data.frame(
  OTU = rownames(otu_mat2),
  Total = rowSums(otu_mat2),
  stringsAsFactors = FALSE
)
df2$TaxString <- taxstr2[df2$OTU]
df2$TaxString[is.na(df2$TaxString)] <- "UNKNOWN_TAX"

# Group by taxonomy and get sorted per-OTU totals (descending)
grouped_sorted <- function(df) {
  df %>%
    group_by(TaxString) %>%
    summarize(
      Num_OTUs = n(),
      Totals = list(sort(Total, decreasing = TRUE)),
      OTUs = list(OTU[order(-Total)]) ,
      .groups = "drop"
    )
}

g1 <- grouped_sorted(df1)
g2 <- grouped_sorted(df2)

# Union of taxonomies
all_tax <- union(g1$TaxString, g2$TaxString)

# Prepare summary table and detect differences
summary_rows <- list()
differing_taxonomies <- list()

for (tax in all_tax) {
  row1 <- g1 %>% filter(TaxString == tax)
  row2 <- g2 %>% filter(TaxString == tax)
  num1 <- if (nrow(row1) == 0) 0 else row1$Num_OTUs
  num2 <- if (nrow(row2) == 0) 0 else row2$Num_OTUs
  totals1 <- if (nrow(row1) == 0) numeric(0) else unlist(row1$Totals)
  totals2 <- if (nrow(row2) == 0) numeric(0) else unlist(row2$Totals)
  # compare sorted vectors exactly
  same <- identical(as.numeric(totals1), as.numeric(totals2))
  summary_rows[[length(summary_rows) + 1]] <- data.frame(
    Taxonomy = tax,
    Num_OTUs_1 = num1,
    Num_OTUs_2 = num2,
    Same_Totals = same,
    stringsAsFactors = FALSE
  )
  if (!same) {
    # include detailed info for this taxonomy
    detail <- list(
      Taxonomy = tax,
      OTUs_1 = if (nrow(row1)==0) character(0) else unlist(row1$OTUs),
      Totals_1 = totals1,
      OTUs_2 = if (nrow(row2)==0) character(0) else unlist(row2$OTUs),
      Totals_2 = totals2
    )
    differing_taxonomies[[length(differing_taxonomies) + 1]] <- detail
  }
}

summary_df <- bind_rows(summary_rows)

cat("=== Taxonomy Comparison (sorted per-OTU totals) ===\n")
cat("Taxonomies in Folder 1:", nrow(g1), " Folder 2:", nrow(g2), "\n")
cat("Taxonomies identical:", sum(summary_df$Same_Totals), "\n")
cat("Taxonomies differing:", sum(!summary_df$Same_Totals), "\n\n")
if (sum(!summary_df$Same_Totals) > 0) {
  cat("Sample differing taxonomies (first 10):\n")
  print(head(summary_df %>% filter(!Same_Totals), 10))
}

# Save summary CSV
write.csv(summary_df, "phyloseq_taxonomy_sorted_comparison_summary.csv", row.names = FALSE)

# Save details for differing taxonomies into a detailed CSV (one block per taxonomy)
if (length(differing_taxonomies) > 0) {
  details_list <- lapply(differing_taxonomies, function(d) {
    # make a tidy data.frame listing each OTU and total in run1 and run2 side-by-side
    n1 <- length(d$OTUs_1); n2 <- length(d$OTUs_2); nmax <- max(n1, n2)
    data.frame(
      Taxonomy = rep(d$Taxonomy, nmax),
      OTU_1 = c(d$OTUs_1, rep(NA, nmax - n1)),
      Total_1 = c(d$Totals_1, rep(NA, nmax - n1)),
      OTU_2 = c(d$OTUs_2, rep(NA, nmax - n2)),
      Total_2 = c(d$Totals_2, rep(NA, nmax - n2)),
      stringsAsFactors = FALSE
    )
  })
  details_df <- bind_rows(details_list)
  write.csv(details_df, "phyloseq_taxonomy_sorted_comparison_differences.csv", row.names = FALSE)
  cat("Detailed differences written to: phyloseq_taxonomy_sorted_comparison_differences.csv\n")
} else {
  cat("No differing taxonomies to write details for.\n")
}

cat("\nSummary CSV: phyloseq_taxonomy_sorted_comparison_summary.csv\n")
