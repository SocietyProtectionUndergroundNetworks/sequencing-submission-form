library(optparse)
library(rmarkdown)
library(pdftools)

# Define options
option_list <- list(
  make_option(
    c("-p", "--project"),
    type = "character",
    default = "",
    help = "Path to r_output ITS1 or ITS2 folder"
  ),
  make_option(
    c("-n", "--name"),
    type = "character",
    default = "",
    help = "Name of project, eg 'sl-atacama'"
  ),
  make_option(
    c("--missing-its"),
    type = "character",
    default = "",
    help = "JSON string of missing its samples"
  ),
  make_option(
    c("--missing-ssu"),
    type = "character",
    default = "",
    help = "JSON string of missing ssu samples"
  ),
  make_option(
    c("-i", "--its"),
    type = "character",
    default = "",
    help = "Name of ITS subfolder eg ITS2 or ITS1"
  ),
  make_option(
    c("-s", "--ssu"),
    type = "character",
    default = "",
    help = "Name of SSU subfolder eg SSU_dada2 or SSU_vsearch"
  )
)

# Parse options
parser <- OptionParser(option_list = option_list)
args <- parse_args(parser, convert_hyphens_to_underscores = TRUE)

# Define Rmd files
intro_rmd <- "report_intro.rmd"
its_rmd <- "report_its.rmd"
ssu_rmd <- "report_ssu.rmd"

# Temporary PDF filenames
intro_pdf <- paste0(args$project, "/r_output/intro.pdf")
its_pdf <- paste0(args$project, "/r_output/its.pdf")
ssu_pdf <- paste0(args$project, "/r_output/ssu.pdf")

# Render the intro (always included)
render(intro_rmd, output_file = intro_pdf, params = list(name = args$name))

# Render ITS report if applicable
if (args$its != "") {
  render(its_rmd, output_file = its_pdf, params = list(project = args$project, its = args$its, missing = args$missing_its))
} else {
  its_pdf <- NULL  # Skip ITS report
}

# Render SSU report if applicable
if (args$ssu != "") {
  render(ssu_rmd, output_file = ssu_pdf, params = list(project = args$project, ssu = args$ssu, missing = args$missing_ssu))
} else {
  ssu_pdf <- NULL  # Skip SSU report
}

# Combine PDFs into a final report
pdf_files <- c(intro_pdf, its_pdf, ssu_pdf)
pdf_files <- pdf_files[!is.null(pdf_files)]  # Remove NULL values

output_pdf <- paste0(args$project, "/r_output/report.pdf")
pdf_combine(pdf_files, output = output_pdf)

unlink(pdf_files)