# Load necessary packages only
library(phyloseq)
library(tidyverse)
library(optparse)
library(decontam)
library(doParallel)
library(iNEXT)
library(janitor)
library(data.table)
library(jsonlite)

# Define options
option_list <- list(
  make_option(
    c("-l", "--lotus2"),
    type = "character",
    default = "/mnt/seq_processed/00057_20241216JXLN0L/lotus2_report/ITS2/",
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
  ),
  make_option(
    c("-e", "--exclude"),
    type = "character",
    #default = '[{"Taxonomy_level": "Family","Value": "Suillaceae"},
    #            {"Taxonomy_level": "Family","Value": "Tricholomataceae"}]',
    default = '',
    help = "JSON string of taxonomy levels and values to exclude when making AMF subset"
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
  physeq.pa.pos <- prune_samples(sample_data(physeq.pa)$Sample_or_Control == "True sample" | sample_data(physeq.pa)$Sample_or_Control == "sample", physeq.pa)

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

# Generate exclude expression from --exclude arg
if (args$exclude != "") {
  exclude_taxa_list <- fromJSON(args$exclude, simplifyDataFrame = FALSE)  # Ensures proper list format
  
  filter_expr <- sapply(exclude_taxa_list, function(x) {
    tax_level <- x$Taxonomy_level  # e.g., "Family" or "Class"
    tax_name <- x[[2]]             # e.g., "Tricholomataceae"
    paste0("!", tax_level, " %in% '", tax_name, "'")  # Negate to exclude taxa
  })
  
  # Combine expressions using "|" (logical OR) to exclude all unwanted taxa
  filter_expr_combined <- paste(filter_expr, collapse = " & ")
} else {
  filter_expr_combined <- "TRUE"
}

##### Extract out ECMs from FungalTraits database and phyloseq object. For this step, you need to have downloaded the file "EcM_guild_assignment_13225_2020_466_MOESM4_ESM.csv" from the SPUN 'project_bioinformatics_and_processing' Github repository

fungaltraits <- read.csv("/usr/src/app/13225_2020_466_MOESM4_ESM.csv")

fungal_traits_ecm <- fungaltraits %>%
  select(Genus, primary_lifestyle) %>%
  filter(primary_lifestyle == "ectomycorrhizal")

# Check how many Genuses are ecm:

num_ecm_genera <- length(which(get_taxa_unique(physeq_filtered, taxonomic.rank = "Genus") %in% fungal_traits_ecm$Genus))

if (num_ecm_genera > 0) {
  # Filter physeq_decontam object by this list of EcM Genus
  # and exclude list if any
  ecm_physeq <- subset_taxa(physeq_decontam, Genus %in% fungal_traits_ecm$Genus) %>%
    subset_taxa(eval(parse(text = filter_expr_combined)))

  # Save file. To open in R use: ecm_physeq <- readRDS("ecm_physeq.Rdata")
  saveRDS(ecm_physeq, file = str_c(args$output, "/", "ecm_physeq.Rdata"))

  p <- plot_bar(ecm_physeq, fill = "Genus")
  ggsave(
    str_c(args$output, "/", "ecm_physeq_by_genus.pdf"), p,
    width = 14, height = 14, units = "in"
  )

  ## ChaoRichness

  ecm_physeq_truesamples <- prune_samples(
    !sample_data(ecm_physeq)$is.neg,
    ecm_physeq
  )

  otu_long <- otu_table(ecm_physeq_truesamples) %>%
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

      if (sum(freq_list) > 1) {
        # Calculate diversity metrics
        calc <- ChaoRichness(x = freq_list, datatype = "abundance", conf = 0.95)
        div <- c(calc, seq_depth = seq_depth)

      } else {
        if (freq_list == 1) {
          div <- c(Observed = 1, Estimator = 1, Est_s.e. = 0,
                   "95% Lower" = 1, "95% Upper" = 1, seq_depth = seq_depth)
        } else {
          div <- c(Observed = 0, Estimator = 0, Est_s.e. = 0,
                   "95% Lower" = 0, "95% Upper" = 0, seq_depth = seq_depth)
        }
      }
    } else {
      div <- c(Observed = NA, Estimator = 0, Est_s.e. = 0,
               "95% Lower" = 0, "95% Upper" = 0, seq_depth = NA)
    }
  }

  as.data.frame(do.call(rbind, div.output)) %>%
    rownames_to_column("sample_id") %>%
    clean_names() %>%
    fwrite(str_c(args$output, "/metadata_chaorichness.csv"))
    
    
  # Extract taxonomy data
  taxonomy_data <- tax_table(ecm_physeq_truesamples) %>%
    as.data.frame() %>%
    rownames_to_column("OTU")

  # Extract OTU data (abundance) from the OTU table
  otu_long <- otu_table(ecm_physeq_truesamples) %>%
    as.data.frame() %>%
    rownames_to_column("OTU") %>%
    pivot_longer(!OTU, names_to = "sample_id", values_to = "abundance") %>%
    filter(abundance != 0)

  # Combine OTU table with taxonomy data
  otu_full_data <- otu_long %>%
    left_join(taxonomy_data, by = "OTU")

  # Export the combined data to a CSV file
  fwrite(otu_full_data, file = str_c(args$output, "/otu_full_data.csv"))
}
