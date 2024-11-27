library(phyloseq)
library(Biostrings)

# Load the RData file
load('/seq_processed/00003_20240904RPGNGG/lotus2_report/ITS2/phyloseq.Rdata')

# Load the DNA sequences
dna_sequences <- readDNAStringSet("/mnt/seq_processed/00003_20240904RPGNGG/lotus2_report/ITS2/OTU.fna")

# Add the DNA sequences to the phyloseq object
physeq <- merge_phyloseq(physeq, refseq(dna_sequences))

# Check the structure of the phyloseq object
str(physeq)

# If you want to extract specific parts of the phyloseq object, do so here.
# For example, you can extract the OTU table:
otu_table <- otu_table(physeq)

# Export the OTU table as a CSV
write.csv(otu_table, '/seq_processed/00003_20240904RPGNGG/lotus2_report/otu_table.csv')

# Similarly, export other components if needed:
write.csv(tax_table(physeq), '/seq_processed/00003_20240904RPGNGG/lotus2_report/taxonomy.csv')
write.csv(sample_data(physeq), '/seq_processed/00003_20240904RPGNGG/lotus2_report/sample_metadata.csv')

# To extract a table with OTU names and OTU sequences
write.csv(refseq(physeq), file = '/seq_processed/00003_20240904RPGNGG/lotus2_report/otu_name_sequence.csv')