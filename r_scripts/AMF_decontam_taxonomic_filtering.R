library(phyloseq); packageVersion("phyloseq")
library(ggplot2); packageVersion("ggplot2")
library(decontam); packageVersion("decontam")
library(DT)
library(tidyverse)
library(readxl)
library(dplyr)

# Get positional args and set [1] working directory, and [2] output dir
args <- commandArgs(trailingOnly = TRUE)
setwd(args[1])
output_dir <- args[2]

## Create a function for loading a phyloseq object
loadRData <- function(fileName){
  #loads an RData file, and returns it
  load(fileName)
  get(ls()[ls() != "fileName"])
}

### Load phyloseq object 
physeq <- loadRData("phyloseq.Rdata")

## Add Read_depth as a variable
sample_data(physeq)$Read_depth <- sample_sums(physeq)

#List read depth
get_variable(physeq, "Read_depth")


###### UNTIL LINE 90, ONLY FOR SAMPLES WITH A NEGATIVE CONTROL ######

### Inspect library sizes

df <- as.data.frame(sample_data(physeq)) # Put sample_data into a ggplot-friendly data.frame
df$LibrarySize <- sample_sums(physeq)
df <- df[order(df$LibrarySize),]
df$Index <- seq(nrow(df))
ggsave(paste0(output_dir,"/","LibrarySize.pdf"),ggplot(data=df, aes(x=Index, y=LibrarySize, color=Sample_or_Control)) + geom_point())


#### WARNING: If no negative control sample labelled 'Control' was included, skip to line 96 ####
## Identify contaminants - prevalence - https://bioconductor.org/packages/devel/bioc/vignettes/decontam/inst/doc/decontam_intro.html#identifying-contaminants-in-marker-gene-and-metagenomics-datasample_data(physeq)$is.neg <- sample_data(physeq)$Sample_or_Control == "Control"
sample_data(physeq)$is.neg <- sample_data(physeq)$Sample_or_Control == "Control"
contamdf.prev.1 <- isContaminant(physeq, method="prevalence", neg="is.neg", threshold=0.1)
table(contamdf.prev.1$contaminant)

## Import required files to assess taxonomy of removed OTUs - for the whole process, we need the 'hiera_BLAST.txt' file and the phyloseq object
classification <- c("kingdom", "phylum", "class", "order", "family", "genus", "species")
otu_taxonomy <- read_delim("hiera_BLAST.txt")
otu_taxonomy_samp <- as.data.frame(otu_taxonomy)
otu_taxonomy <- otu_taxonomy_samp[,-1]
rownames(otu_taxonomy) <- otu_taxonomy_samp[,1]
colnames(otu_taxonomy) <- classification


# Make phyloseq object of presence-absence in negative controls and true samples
physeq.pa <- transform_sample_counts(physeq, function(abund) 1*(abund>0))
physeq.pa.neg <- prune_samples(sample_data(physeq.pa)$Sample_or_Control == "Control", physeq.pa)
physeq.pa.pos <- prune_samples(sample_data(physeq.pa)$Sample_or_Control == "True sample", physeq.pa)
# Make data.frame of prevalence in positive and negative samples
df.pa <- data.frame(pa.pos=taxa_sums(physeq.pa.pos), pa.neg=taxa_sums(physeq.pa.neg),
                    contaminant=contamdf.prev.1$contaminant)
ggsave(paste0(output_dir,"/","control_vs_sample.pdf"),ggplot(data=df.pa, aes(x=pa.neg, y=pa.pos, color=contaminant)) + geom_point() +
  xlab("Prevalence (Negative Controls)") + ylab("Prevalence (True Samples)"))


## Extract the taxonomic classifications of the identified contaminants

row_indices <- which(contamdf.prev.1$contaminant) #grab the row indices that correspond with identified contaminants to locate taxonomic information in the corresponding OTU file

taxonomy_table <- tibble()

for (i in row_indices){
  loc <-  contamdf.prev.1[i, 0]
  tax_key <- row.names(loc)
  tax_value <- otu_taxonomy[tax_key, ]
  taxonomy_table <- rbind(taxonomy_table, tax_value)
}

names(taxonomy_table) <- classification
datatable(taxonomy_table)

## Prune contaminant taxa from the phyloseq tax_table
physeq_decontam <- prune_taxa(!contamdf.prev.1$contaminant, physeq)

## Save file. Note: this must be opened in R using: phyoseq_decontam <- readRDS("physeq_decontam.Rdata")
saveRDS(physeq_decontam, file=paste0(output_dir,"/","physeq_decontam.Rdata"))

## Move the pre-decontaminated phyloseq object into a folder labelled 'pre_decontam'
# dir.create("pre_decontam")
# file.rename(from="phyloseq.Rdata",to="pre_decontam/phyloseq.Rdata")

                                     
####  Create rarefaction curves for the samples #### 

# Remove samples with fewer than a certain number of reads
physeq_filtered <- prune_samples(sample_sums(physeq_decontam) >= 10, physeq_decontam)

# Check the new sample sizes
sample_sums(physeq_filtered)

source("https://raw.githubusercontent.com/mahendra-mariadassou/phyloseq-extended/master/load-extra-functions.R")

p <- ggrare(physeq_filtered,
            step = 500,
            color = "Sample",
            plot = T,
            parallel = T,
            se = F)


p <- p + 
  theme_minimal() +  # Remove grid background
  labs(
    title = "Rarefaction Curves",
    x = "Number of Sequences",
    y = "Richness"
  )

plot(p)
pdf(paste0(output_dir,"/","filtered_rarefaction.pdf"))


## Subset filtered phloseq object to include only the three classes of Mucoromycota that are AMF: "Glomeromycetes", "Archaeosporomycetes" and "Paraglomeromycetes" 

amf_physeq <- physeq%>% subset_taxa(Class =="Glomeromycetes" | Class ==  "Archaeosporomycetes" | Class ==  "Paraglomeromycetes" )

## Save file. Note: this must be opened in R using: amf_physeq <- readRDS("physeq_decontam.Rdata")
saveRDS(amf_physeq, file=paste0(output_dir,"/","amf_physeq.Rdata"))

## Test and explore
plot_bar(amf_physeq, fill="Genus")
pdf(paste0(output_dir,"/","amf_physeq_by_genus.pdf"))