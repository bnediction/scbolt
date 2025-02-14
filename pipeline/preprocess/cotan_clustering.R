#!/usr/bin/Rscript

options(
  needs.promptUser=FALSE,
  parallelly.fork.enable=TRUE
)

pkgs.to.load <- c(
  "optparse",
  "COTAN",
  "zeallot",
  "rlang",
  "data.table",
  "Rtsne",
  "GEOquery",
  "ComplexHeatmap",
  "torch"
)
pkgs.to.install <- pkgs.to.load[!(pkgs.to.load %in% installed.packages()[,"Package"])]

if (length(pkgs.to.install)>0) {
  install.packages(pkgs.to.install)
}
for (pkg in pkgs.to.load) {
  suppressPackageStartupMessages(library(pkg, character.only = TRUE))
}

description <- ""
usage <- ""
arguments <- list(
  make_option("--infile",
              dest="infile",
              type="character",
              default=NULL,
              metavar="FILE",
              help="counting file (csv format)",
              ),
  make_option("--outpath",
              dest="outpath",
              type="character",
              default=NULL,
              metavar="PATH",
              help="output path"
              ),
  make_option("--sep",
              dest="sep",
              type="character",
              action="store",
              default="\t",
              metavar="CHAR",
              help="field delimiter for csv infile (default: `\\t`)"
              ),
  make_option("--condition",
              dest="condition",
              type="character",
              action="store",
              default=NULL,
              metavar="LITERAL",
              help="sample condition"
  )
)

parser <- OptionParser(
  description=description,
  usage=usage,
  option_list=arguments,
  )
args <- parse_args(parser)

args$infile <- "/tmp/RtmpJByYY8/GSM2861514/GSM2861514_E175_Only_Cortical_Cells_DGE.txt.gz"
args$outpath <- "tmp"
args$sep <- "\t"

if (is.null(args$infile)) {
  stop("`--infile` argument is not specified.")
} else if (is.null(args$outpath)) {
  stop("`--outpath` argument is not specified.")
}

dir.create(
  path=file.path(dataDir, GEO),
  showWarnings=FALSE,
  recursive=TRUE
)

setLoggingFile(file.path(args$output, "cotan.log"))

print("Loading data...")

df <- read.csv(
  args$infile,
  sep=args$sep,
  row.names=1L
)

print("COTAN pipeline")

condition <- "mouse_cortex_E17.5"
GEO <- "GSM2861514"

cotan.data <- COTAN(raw=df)
cotan.data <- initializeMetaDataset(
  cotan.data,
  sequencingMethod = "rna_seq",
  GEO=GEO,
  sampleCondition = args$condition
)

plot(ECDPlot(cotan.data))
plot(cellSizePlot(cotan.data))
plot(genesSizePlot(cotan.data))
plot(scatterPlot(cotan.data))

cotan.data <- addElementToMetaDataset(cotan.data, "Num drop B group", 0)
cotan.data <- clean(cotan.data)

c(pcaCellsPlot, pcaCellsData, genesPlot,
  UDEPlot, nuPlot, zoomedNuPlot) %<-% cleanPlots(cotan.data)

plot(pcaCellsPlot)
plot(genesPlot)

cells.to.remove <- rownames(pcaCellsData)[pcaCellsData[["groups"]] == "B"]
cotan.data <- dropGenesCells(cotan.data, cells = cells.to.remove)

cotan.data <- addElementToMetaDataset(
  cotan.data,
  tag="Num drop B group",
  value=1
)
cotan.data <- clean(cotan.data)

c(pcaCellsPlot, pcaCellsData, genesPlot,
  UDEPlot, nuPlot, zoomedNuPlot) %<-% cleanPlots(cotan.data)

plot(pcaCellsPlot)
plot(UDEPlot)
plot(nuPlot)
plot(zoomedNuPlot)

UDE.low.threshold <- 0.30
cotan.data <- addElementToMetaDataset(
  cotan.data,
  tag="Low UDE cells' threshold",
  value=UDE.low.threshold
)

cotan.data <- addElementToMetaDataset(cotan.data, "Num drop B group", 2)

cells.to.remove <- getCells(cotan.data)[getNu(cotan.data) < UDELowThr]
cotan.data <- dropGenesCells(
  cotan.data,
  cells=cells.to.remove
)

### To drop ###

fName <- "GSM2861514_E175_Only_Cortical_Cells_DGE.txt.gz"

dataSetFile <- file.path(dataDir, GEO, fName)

c(useTorch, device) %<-% COTAN:::canUseTorch(TRUE, "cuda")
if (useTorch) {
  message("`torch` library available")
  if (device == "cuda") {
    message("`torch` library can use the `CUDA` GPU")
  } else {
    message("`torch` library can only use the CPU")
    message("Please ensure you have the `OpenBLAS` libraries",
            " installed on the system")
  }
}

