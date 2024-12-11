# Load necessary packages only
library(phyloseq)
library(tidyverse)
library(optparse)
library(decontam)

# Define options
option_list <- list(
  make_option(
    c("-l", "--lotus2 "),
    type = "character",
    default = "/mnt/seq_processed/00051_20241208YWHTXA/lotus2_report/ITS2/",
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
load(str_c(args$lotus2,"/","phyloseq.Rdata"))

## Inspect library sizes
df <- sample_data(physeq)
df$LibrarySize <- sample_sums(physeq)
df <- df[order(df$LibrarySize),]
df$Index <- seq(nrow(df))
ggplot(data=df, aes(x=Index, y=LibrarySize, color=Sample_or_Control)) +
  geom_point()

ggsave(str_c(args$output,"/","LibrarySize.pdf"),
       width = 7, height = 7, units = "in")
       
## Import required files to assess taxonomy of removed OTUs - for the whole process, we need the 'hiera_BLAST.txt' file and the phyloseq object
otu_taxonomy <- read_tsv(str_c(args$lotus2,"/","hiera_BLAST.txt")) %>%
  set_names("OTU", "kingdom", "phylum", "class", "order", "family", "genus", "species")

# If there are no controls, or if the read depth of any control species is in the 75th percentils, store in a variable and print warning
num_of_controls <- df %>% as_tibble %>% filter(Sample_or_Control == "Control") %>% nrow()

if (num_of_controls > 0) {
  # Make phyloseq object of presence-absence in negative controls and true samples
  physeq.pa <- transform_sample_counts(physeq, function(abund) 1*(abund>0))
  physeq.pa.neg <- prune_samples(sample_data(physeq.pa)$Sample_or_Control == "Control", physeq.pa)
  physeq.pa.pos <- prune_samples(sample_data(physeq.pa)$Sample_or_Control == "True sample", physeq.pa)

  ## Extract the taxonomic classifications of the identified contaminants
  sample_data(physeq)$is.neg <- sample_data(physeq)$Sample_or_Control == "Control"
  contamdf.prev.1 <- isContaminant(physeq, method="prevalence", neg="is.neg", threshold=args$threshold)
  contaminant_otus <- contamdf.prev.1 %>% filter(contaminant== TRUE) %>% rownames()
  contaminants <- otu_taxonomy %>%
    filter(OTU %in% contaminant_otus)
  write_csv(contaminants, str_c(args$output,"/","contaminants.csv"))
  
  # Make data.frame of prevalence in positive and negative samples
  df.pa <- data.frame(
    pa.pos=taxa_sums(physeq.pa.pos),
    pa.neg=taxa_sums(physeq.pa.neg),
    contaminant=contamdf.prev.1$contaminant)
  
  ggplot(data=df.pa, aes(x = pa.neg, y = pa.pos, color = contaminant)) +
    geom_point() +
    xlab("Prevalence (Negative Controls)") +
    ylab("Prevalence (True Samples)")

  ggsave(str_c(args$output, "/", "control_vs_sample.pdf"),
         width = 7, height = 7, units = "in")

  # Prune contaminant taxa from the phyloseq tax_table
  physeq_decontam <- prune_taxa(!contamdf.prev.1$contaminant, physeq)

  # Save file. To open in R use:
  # physeq_decontam <- readRDS("physeq_decontam.Rdata")

  saveRDS(physeq_decontam, file=str_c(args$output,"/","physeq_decontam.Rdata"))

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

# Remove samples with fewer than a certain number of reads
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
  str_c(args$output, "/", "filtered_rarefaction.pdf"),
  width = 7, height = 7, units = "in"
)

##### Extract out ECMs from FungalTraits database and phyloseq object. For this step, you need to have downloaded the file "EcM_guild_assignment_13225_2020_466_MOESM4_ESM.csv" from the SPUN 'project_bioinformatics_and_processing' Github repository

fungaltraits <- read.csv("/usr/src/app/13225_2020_466_MOESM4_ESM.csv")

fungal_traits_ecm <- fungaltraits %>%
  select(Genus, primary_lifestyle) %>% 
  filter(primary_lifestyle == "ectomycorrhizal")

# add sanity checks? No need as this only needs to be done the first time

# Filter physeq_decontam object by this list of EcM Genus
ecm_physeq = subset_taxa(physeq_decontam, Genus %in% fungal_traits_ecm$Genus)

# Save file. To open in R use: ecm_physeq <- readRDS("ecm_physeq.Rdata")
saveRDS(ecm_physeq, file=str_c(args$output, "/", "ecm_physeq.Rdata"))

plot_bar(ecm_physeq, fill = "Genus")
ggsave(
  str_c(args$output, "/", "ecm_physeq_by_genus.pdf"),
  width = 14, height = 14, units = "in"
)

sample_variables(ecm_physeq)
sample_names(ecm_physeq)
sort(sample_sums(ecm_physeq))