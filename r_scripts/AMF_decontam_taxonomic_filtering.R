# Load necessary packages only
library(phyloseq)
library(tidyverse)
library(optparse)
library(decontam)
library(doParallel)
library(iNEXT)
library(janitor)
library(data.table)

# Define options
option_list <- list(
  make_option(
    c("-l", "--lotus2 "),
    type = "character",
    default = "/mnt/seq_processed/00035_20241126HNS0O7/lotus2_report/SSU_vsearch/",
    help = "Path to lotus2 output folder"
  ),
  make_option(
    c("-o", "--output"),
    type = "character",
    default = "~/test2",
    help = "Path to output folder"
  ),
  make_option(
    c("-t", "--threshold"),
    type = "double",
    default = 0.1,
    help = "Threshold for detecting contamination (proportion between 0 and 1)"
  ),
  make_option(
    c("-m", "--multiqc"),
    type = "character",
    default = "",
    help = "Path to multiqc parent folder containing multiqc_plots"
  ),
  make_option(
    c("-r", "--readmin"),
    type = "integer",
    default = 10,
    help = "Minimum number of reads for a sample to be included in rarefaction curves"
  )
)

# Parse options
parser <- OptionParser(option_list = option_list)
args <- parse_args(parser)

# Load phyloseq object
load(str_c(args$lotus2, "/", "phyloseq.Rdata"))

## Inspect library sizes
df <- sample_data(physeq)
df$LibrarySize <- sample_sums(physeq)
df <- df[order(df$LibrarySize), ]
df$Index <- seq_len(nrow(df))

# Add Library size / seq_depth to physeq object
sample_data(physeq)$LibrarySize <- sample_sums(physeq)

# Plot library size in increasing order
p <- ggplot(data = df, aes(x = Index, y = LibrarySize, color = Sample_or_Control)) +
  geom_point()

ggsave(str_c(args$output, "/", "LibrarySize.pdf"), p,
       width = 7, height = 7, units = "in")

## Import required files to assess taxonomy of removed OTUs - for the whole process, we need the 'hiera_BLAST.txt' file and the phyloseq object
otu_taxonomy <- read_tsv(str_c(args$lotus2, "/", "hiera_BLAST.txt")) %>%
  set_names("OTU", "kingdom", "phylum", "class", "order", "family", "genus", "species")

# If there are no controls, or if the read depth of any control species is in the 75th percentils, store in a variable and print warning

num_of_controls <- df %>% as_tibble %>% filter(Sample_or_Control == "Control") %>% nrow()

sample_data(physeq)$is.neg <- (sample_data(physeq)$Sample_or_Control == "Control")

if (num_of_controls > 0) {
  # Make phyloseq object of presence-absence in negative controls and true samples
  physeq.pa <- transform_sample_counts(physeq, function(abund) 1 * (abund > 0))
  physeq.pa.neg <- prune_samples(sample_data(physeq.pa)$Sample_or_Control == "Control", physeq.pa)
  physeq.pa.pos <- prune_samples(sample_data(physeq.pa)$Sample_or_Control == "True sample", physeq.pa)

  ## Extract the taxonomic classifications of the identified contaminants
  contamdf <- isContaminant(physeq, method = "prevalence", neg = "is.neg", threshold = args$threshold)
  contaminant_otus <- contamdf %>% filter(contaminant == TRUE) %>% rownames()
  contaminants <- otu_taxonomy %>%
    filter(OTU %in% contaminant_otus)
  write_csv(contaminants, str_c(args$output, "/", "contaminants.csv"))

  # Make data.frame of prevalence in positive and negative samples
  df.pa <- data.frame(
    pa.pos = taxa_sums(physeq.pa.pos),
    pa.neg = taxa_sums(physeq.pa.neg),
    contaminant = contamdf$contaminant)

  p <- ggplot(data = df.pa, aes(x = pa.neg, y = pa.pos, color = contaminant)) +
    geom_point() +
    xlab("Prevalence (Negative Controls)") +
    ylab("Prevalence (True Samples)")

  ggsave(str_c(args$output, "/", "control_vs_sample.pdf"), p,
         width = 7, height = 7, units = "in")

  # Prune contaminant taxa from the phyloseq tax_table
  physeq_decontam <- prune_taxa(!contamdf$contaminant, physeq)

  # Save file. To open in R use:
  # physeq_decontam <- readRDS("physeq_decontam.Rdata")

  saveRDS(physeq_decontam, file = str_c(args$output, "/", "physeq_decontam.Rdata"))

  percentile_of_control <- df %>%
    as_tibble %>%
    mutate(percentile = percent_rank(LibrarySize) * 100) %>%
    filter(Sample_or_Control == "Control") %>%
    pull(percentile) %>%
    last()

} else {
  physeq_decontam <- physeq
}

####  Create rarefaction curves for the samples ####

# Keep only true samples, and samples with more than a certain minimum number of reads
physeq_filtered <- prune_samples(
  sample_sums(physeq_decontam) >= args$readmin,
  physeq_decontam
)

# Check the new sample sizes
sample_sums(physeq_filtered)

source("https://raw.githubusercontent.com/mahendra-mariadassou/phyloseq-extended/master/load-extra-functions.R")

p <- ggrare(
  physeq_filtered,
  step = 500,
  color = "Sample",
  plot = TRUE,
  parallel = TRUE,
  se = FALSE
)

p <- p +
  theme_minimal() +  # Remove grid background
  labs(
    title = "Rarefaction Curves",
    x = "Number of Sequences",
    y = "Richness"
  )

plot(p)
ggsave(
  str_c(args$output, "/", "filtered_rarefaction.pdf"), p,
  width = 7, height = 7, units = "in"
)

## Subset decontam phloseq object to include only the three classes of Mucoromycota that are AMF: "Glomeromycetes", "Archaeosporomycetes" and "Paraglomeromycetes" 

amf_physeq <- physeq_decontam %>% subset_taxa(Class == "Glomeromycetes" | Class ==  "Archaeosporomycetes" | Class ==  "Paraglomeromycetes")

# Save file. To open in R use: amf_physeq <- readRDS("amf_physeq.Rdata")
saveRDS(amf_physeq, file = str_c(args$output, "/", "amf_physeq.Rdata"))

p <- plot_bar(amf_physeq, fill = "Genus")
plot(p)
ggsave(
  str_c(args$output, "/", "amf_physeq_by_genus.pdf"), p,
  width = 14, height = 14, units = "in"
)

## ChaoRichness

amf_physeq_truesamples <- prune_samples(
  !sample_data(amf_physeq)$is.neg,
  amf_physeq
)

otu_long <- otu_table(amf_physeq_truesamples) %>%
  as.data.frame() %>%
  rownames_to_column("OTU") %>%
  pivot_longer(!OTU, names_to = "sample_id", values_to = "abundance") %>%
  filter(abundance != 0)

div.output <- foreach(i = unique(otu_long$sample_id), .final = function(i) setNames(i, unique(otu_long$sample_id))) %do% {
  freq_list <- otu_long %>%
    filter(sample_id == i) %>%
    select(-sample_id) %>%
    pull(abundance)

  if (length(freq_list) > 0) {
    seq_depth <- sample_data(physeq)[i]$LibrarySize

    # Calculate diversity metrics
    calc <- ChaoRichness(x = freq_list, datatype = "abundance", conf = 0.95)
    div <- c(calc, seq_depth = seq_depth)
  }
}

as.data.frame(do.call(rbind, div.output)) %>%
  rownames_to_column("sample_id") %>%
  clean_names() %>%
  fwrite(str_c(args$output, "/metadata_chaorichness.csv"))
