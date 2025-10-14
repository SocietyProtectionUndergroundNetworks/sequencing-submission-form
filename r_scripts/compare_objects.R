#!/usr/bin/env Rscript

# Usage:
# Rscript r_scripts/compare_objects_detailed.R path/to/folder1 path/to/folder2

args <- commandArgs(trailingOnly = TRUE)
if(length(args) != 2) stop("Please provide exactly two folder paths as arguments.")

folder1 <- args[1]
folder2 <- args[2]

file1 <- file.path(folder1, "phyloseq.Rdata")
file2 <- file.path(folder2, "phyloseq.Rdata")

if(!file.exists(file1)) stop(paste("File not found:", file1))
if(!file.exists(file2)) stop(paste("File not found:", file2))

suppressPackageStartupMessages(library(phyloseq))
suppressPackageStartupMessages(library(dplyr))

# Load phyloseq object from Rdata
load_phyloseq <- function(file) {
  env <- new.env()
  load(file, envir = env)
  objs <- ls(env)
  ps_obj <- NULL
  for(obj in objs) {
    if(inherits(env[[obj]], "phyloseq")) {
      ps_obj <- env[[obj]]
      break
    }
  }
  if(is.null(ps_obj)) stop(paste("No phyloseq object found in", file))
  return(ps_obj)
}

ps1 <- load_phyloseq(file1)
ps2 <- load_phyloseq(file2)

# Summarize basic statistics
summarize_phyloseq <- function(ps) {
  otu_mat <- as(otu_table(ps), "matrix")
  data.frame(
    OTUs = nrow(otu_mat),
    Samples = ncol(otu_mat),
    TotalReads = sum(otu_mat),
    MinAbundance = min(otu_mat),
    MaxAbundance = max(otu_mat),
    MeanAbundance = mean(otu_mat)
  )
}

cat("=== Summary Statistics ===\n")
cat("Folder 1:\n")
print(summarize_phyloseq(ps1))
cat("\nFolder 2:\n")
print(summarize_phyloseq(ps2))
cat("\n")

# Detailed differences in OTUs
compare_otus <- function(ps1, ps2) {
  otu1 <- as.data.frame(as(otu_table(ps1), "matrix"))
  otu2 <- as.data.frame(as(otu_table(ps2), "matrix"))

  otu1_names <- rownames(otu1)
  otu2_names <- rownames(otu2)

  cat("=== OTU Differences ===\n")
  cat("OTUs only in Folder 1:", length(setdiff(otu1_names, otu2_names)), "\n")
  cat("OTUs only in Folder 2:", length(setdiff(otu2_names, otu1_names)), "\n\n")

  common_otus <- intersect(otu1_names, otu2_names)
  if(length(common_otus) > 0) {
    diffs <- sapply(common_otus, function(otu) {
      sum(otu1[otu, ] != otu2[otu, ])
    })
    diffs <- diffs[diffs > 0]
    cat("Number of OTUs with differing abundances:", length(diffs), "\n")
    if(length(diffs) > 0) {
      cat("Sample of differences (first 10 OTUs):\n")
      print(head(diffs, 10))
    }
  }
}

# Compare taxonomy
compare_tax <- function(ps1, ps2) {
  tax1 <- as.data.frame(as(tax_table(ps1), "matrix"))
  tax2 <- as.data.frame(as(tax_table(ps2), "matrix"))

  cat("\n=== Taxonomy Differences ===\n")
  tax1_otus <- rownames(tax1)
  tax2_otus <- rownames(tax2)
  cat("Taxonomy only in Folder 1:", length(setdiff(tax1_otus, tax2_otus)), "\n")
  cat("Taxonomy only in Folder 2:", length(setdiff(tax2_otus, tax1_otus)), "\n\n")
  
  common_otus <- intersect(tax1_otus, tax2_otus)
  if(length(common_otus) > 0) {
    diffs <- sapply(common_otus, function(otu) {
      any(tax1[otu, ] != tax2[otu, ])
    })
    diffs <- diffs[diffs]
    cat("Number of OTUs with differing taxonomy:", length(diffs), "\n")
    if(length(diffs) > 0) {
      cat("Sample OTUs with taxonomy differences (first 10):\n")
      print(head(names(diffs), 10))
    }
  }
}

# Run comparisons
compare_otus(ps1, ps2)
compare_tax(ps1, ps2)

# Compare phylogenetic tree presence
cat("\n=== Phylogenetic Tree Comparison ===\n")
tree1 <- phy_tree(ps1)
tree2 <- phy_tree(ps2)
if(is.null(tree1) || is.null(tree2)) {
  cat("One or both objects have no phylogenetic tree.\n")
} else {
  equal <- all.equal(tree1, tree2)
  if(isTRUE(equal)) cat("Phylogenetic trees are identical.\n") else cat("Phylogenetic trees differ.\n")
}
