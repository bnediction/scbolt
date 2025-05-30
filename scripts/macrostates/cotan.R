#!/usr/bin/Rscript

options(
  needs.promptUser=FALSE,
  parallelly.fork.enable=TRUE
)

pkgs.to.load <- c(
  "rstan",
  "optparse",
  "COTAN",
  "zeallot",
  "rlang",
  "data.table",
  "Rtsne",
  "GEOquery",
  "ComplexHeatmap",
  "torch",
  "Seurat"
)
pkgs.to.install <- pkgs.to.load[!(pkgs.to.load %in% installed.packages()[,"Package"])]

if (length(pkgs.to.install)>0) {
  install.packages(pkgs.to.install, repos = "http://cran.us.r-project.org")
}
for (pkg in pkgs.to.load) {
  suppressPackageStartupMessages(library(pkg, character.only = TRUE))
}

datetime.now.POSIXct <- function()
  format(Sys.time(), format='%Y-%m-%d %H:%M:%S')

print_task <- function(msg, logfile.name){
  closeAllConnections()
  cat(paste0(datetime.now.POSIXct()," - TASK - ",msg,"\n"))
  logfile <- file(logfile.name, open="a")
  sink(logfile, type="output")
  sink(logfile, type="message")
}

print_result <- function(msg, logfile.name){
  closeAllConnections()
  cat(paste0(datetime.now.POSIXct()," - RESULT - ",msg,"\n"))
  logfile <- file(logfile.name, open="a")
  sink(logfile, type="output")
  sink(logfile, type="message")
}

print_info <- function(msg, logfile.name){
  closeAllConnections()
  cat(paste0(datetime.now.POSIXct()," - INFO - ",msg,"\n"))
  logfile <- file(logfile.name, open="a")
  sink(logfile, type="output")
  sink(logfile, type="message")
}

print_debug <- function(msg, logfile.name){
  closeAllConnections()
  cat(paste0(datetime.now.POSIXct()," - DEBUG - ",msg,"\n"))
  logfile <- file(logfile.name, open="a")
  sink(logfile, type="output")
  sink(logfile, type="message")
}

print_warning <- function(msg, logfile.name){
  closeAllConnections()
  cat(paste0(datetime.now.POSIXct()," - WARNING - ",msg,"\n"))
  logfile <- file(logfile.name, open="a")
  sink(logfile, type="output")
  sink(logfile, type="message")
}

is.defined = function(x)
  !is.null(x)

description <- ""
usage <- ""
arguments <- list(
  make_option("--infile",
              dest="infile",
              type="character",
              default=NULL,
              metavar="FILE",
              help="input file storing counts (format: csv, required)",
              ),
  make_option("--outfile",
              dest="outfile",
              type="character",
              default=NULL,
              metavar="FILE",
              help="output file storing cotan object (format: RDS, required)"
              ),
  make_option("--csv",
              dest="csv",
              type="character",
              default=NULL,
              metavar="FILE",
              help="output file storing cotan macrostates (format: csv)"
  ),
  make_option("--sep",
              dest="sep",
              type="character",
              action="store",
              default="\t",
              metavar="CHAR",
              help="field delimiter for csv infile (default: `\\t`)"
              ),
  make_option("--name",
              dest="name",
              type="character",
              action="store",
              default="reference",
              metavar="LITERAL",
              help="dataset name (default: reference)"
  ),
  make_option("--drop-mithocondrial",
              dest="drop_mithocondrial",
              action="store_true",
              default=FALSE,
              help="drop mithocondrial genes (default: false)"
  ),
  make_option("--min-expression",
              dest="min_expression",
              type="integer",
              action="store",
              default=NULL,
              metavar="INT",
              help="minimum number of expressed genes required for a cell to pass filtering, potentially being dead (default: none)"
  ),
  make_option("--max-expression",
              dest="max_expression",
              type="integer",
              action="store",
              default=NULL,
              metavar="INT",
              help="maximum number of expressed genes required for a cell to pass filtering, potentially being multiplets (default: none)"
  ),
  make_option("--min-reads",
              dest="min_reads",
              type="integer",
              action="store",
              default=NULL,
              metavar="INT",
              help="minimum number of reads required for a cell to pass filtering, potentially being dead (default: none)"
  ),
  make_option("--max-reads",
              dest="max_reads",
              type="integer",
              action="store",
              default=NULL,
              metavar="INT",
              help="maximum number of reads required for a cell to pass filtering, potentially being multiplets (default: none)"
  ),
  make_option("--mithocondrial-threshold",
              dest="mithocondrial_threshold",
              type="double",
              action="store",
              default=NULL,
              metavar="[0-1]",
              help="maximum proportion of expressed genes encoding mithocondrion proteins required for a cell to pass filtering, potentially being dead (default: none)"
  ),
  make_option("--cotan-filtering",
              dest="cotan_filtering",
              action = "store_true",
              default = FALSE,
              help = "drop cell outliers (default: false)"
  ),
  make_option("--min-ude",
              dest="min_ude",
              type="double",
              action="store",
              default=NULL,
              metavar="[0-1]",
              help="minimum UMI detection efficiency (UDE) required for a cell to pass filtering, potentially being dead (recommended: 0.3, default: none)"
  ),
  make_option("--max-iterations",
              dest="max_iterations",
              type="integer",
              action="store",
              default=25,
              metavar="INT",
              help="maximum iteration number for merging clustering (default: 25)"
  ),
  make_option("--method",
              dest="method",
              type="character",
              action="store",
              default="classic",
              metavar="[classic|soft-merging|strong-merging]",
              help="method for computing cotan clusters: soft-merging and strong-merging merge uniform clusters (default: classic)"
  ),
  make_option("--jobs",
              dest="jobs",
              type="integer",
              action="store",
              default=1,
              metavar="INT",
              help="number of allocated processors (default: 1)"
  )
)

parser <- OptionParser(
  description=description,
  usage=usage,
  option_list=arguments,
  )
args <- parse_args(parser)

if (is.null(args$infile)) {
  stop("option --infile required but not specified")
} else if (is.null(args$outfile)) {
  stop("option --outfile required but not specified")
} else if (args$method %notin% c("classic", "soft-merging", "strong-merging")){
  stop(paste0("`--method` argument can only take one of the following values: 'classic', 'soft-merging', 'strong-merging' (value: ",args$method,")"))
}

outpath <- dirname(args$outfile)
logfile.name <- file.path(outpath, "cotan.log")
logfile <- file(logfile.name, open="wt")
sink(logfile, type="output")
sink(logfile, type="message")
print_debug(paste0("storing running cotan-related information in ", logfile.name), logfile.name)

dir.create(
  path=outpath,
  showWarnings=FALSE,
  recursive=TRUE
)

print_task(paste0("loading file ", args$infile), logfile.name)

df <- read.csv(
  args$infile,
  sep=args$sep,
  row.names=1L
)

cotan <- COTAN(raw=df)
cotan <- initializeMetaDataset(
  cotan,
  sequencingMethod = "rna_seq",
  GEO=NULL,
  sampleCondition = args$condition
)

print_task("preprocessing counting data", logfile.name)

if (isTRUE(args$drop_mithocondrial)){
  cotan <- addElementToMetaDataset(cotan, tag="remove mithocondrial genes and cells", value=TRUE)
  genes.to.remove <- getGenes(cotan)[grep("^Mt", getGenes(cotan))]
  cells.to.remove <- getCells(cotan)[which(getCellsSize(cotan) == 0L)]
  cotan <- dropGenesCells(cotan, genes.to.remove, cells.to.remove)
} else {
  cotan <- addElementToMetaDataset(cotan, tag="remove mithocondrial genes and cells", value=FALSE)
}

if (is.defined(args$min_reads))
{
  cotan <- addElementToMetaDataset(cotan, tag="minimum read threshold", value=args$min_reads)
  cells.to.remove <- getCells(cotan)[getCellsSize(cotan) < args$min_reads]
  cotan <- dropGenesCells(cotan, cells = cells.to.remove)
}

if (is.defined(args$max_reads))
{
  cotan <- addElementToMetaDataset(cotan, tag="maximum read threshold", value=args$max_reads)
  cells.to.remove <- getCells(cotan)[getCellsSize(cotan) > args$max_reads]
  cotan <- dropGenesCells(cotan, cells = cells.to.remove)
}

if (is.defined(args$min_expression))
{
  cotan <- addElementToMetaDataset(cotan, tag="minimum gene expression threshold", value=args$min_expression)
  cells.to.remove <- getCells(cotan)[getNumExpressedGenes(cotan) < args$min_expression]
  cotan <- dropGenesCells(cotan, cells = cells.to.remove)
}

if (is.defined(args$max_expression))
{
  cotan <- addElementToMetaDataset(cotan, tag="maximum gene expression threshold", value=args$max_expression)
  cells.to.remove <- getCells(cotan)[getNumExpressedGenes(cotan) > args$max_expression]
  cotan <- dropGenesCells(cotan, cells = cells.to.remove)
}

if (is.defined(args$mithocondrial_threshold)){
  cotan <- addElementToMetaDataset(cotan, "mithocondrial percentage threshold", args$mithocondrial_threshold)
  c(mitochondrial.plot, mitochondrial.sizes) %<-% mitochondrialPercentagePlot(cotan, genePrefix = "^Mt")
  cells.to.remove <- rownames(mitochondrial.sizes)[mitochondrial.sizes[["mit.percentage"]] > args$mithocondrial_threshold]
  cotan <- dropGenesCells(cotan, cells = cells.to.remove)
}
  
if (isTRUE(args$cotan_filtering)){
  cotan <- addElementToMetaDataset(cotan, tag="cotan filtering", value=TRUE)
  cotan <- clean(cotan)
  c(pca.plot, pca.data, genes.plot, UDE.plot, nu.plot, zoomed.nu.plot) %<-% cleanPlots(cotan)
  
  cells.to.remove <- rownames(pca.data)[pca.data[["groups"]] == "B"]
  cotan <- dropGenesCells(cotan, cells = cells.to.remove)

  cotan <- clean(cotan)
  
  cotan <- addElementToMetaDataset(cotan, "minimum UDE cell threshold", args$min_ude)
  cells.to.remove <- getCells(cotan)[getNu(cotan) < args$min_ude]
  cotan <- dropGenesCells(cotan, cells = cells.to.remove)
} else {
  cotan <- addElementToMetaDataset(cotan, tag="cotan filtering", value=FALSE)
}

print_task("initializing cotan settings", logfile.name)

cotan <- clean(cotan)
c(pca.plot, pca.data, genes.plot, UDE.plot, nu.plot, zoomed.nu.plot) %<-% cleanPlots(cotan)

c(can.use.torch, device) %<-% COTAN:::canUseTorch(TRUE, "cuda")

cotan <- proceedToCoex(
  cotan,
  calcCoex=TRUE,
  optimizeForSpeed=if (can.use.torch == TRUE && device=="cuda") TRUE else FALSE,
  cores=args$jobs,
  device=device,
  saveObj=FALSE,
  outDir=outpath
)

global.differentiation.index <- calculateGDI(cotan)
cotan <- storeGDI(
  cotan,
  genesGDI=global.differentiation.index
)

print_task("clustering cells using cotan algorithm", logfile.name)

advanced.GDI.uniformity.checker <- new("AdvancedGDIUniformityCheck")

print_info("searching for uniform clusters", logfile.name)
print_warning("this may take some time.", logfile.name)

c(split.clusters, split.coex.df) %<-%
  cellsUniformClustering(
    cotan,
    initialResolution=0.8,
    maxIterations=args$max_iterations,
    checker=advanced.GDI.uniformity.checker,
    optimizeForSpeed=if (can.use.torch == TRUE && device=="cuda") TRUE else FALSE,
    deviceStr=device,
    cores=args$jobs,
    saveObj=FALSE,
    outDir=outpath
  )
cotan <- addClusterization(
  cotan,
  clName="split",
  clusters=split.clusters,
  coexDF=split.coex.df
)

if (args$method == "classic"){
  c(clusters, coex.df) %<-%
    list(split.clusters, split.coex.df)
} else if (args$method == "soft-merging"){
  print_info("merging uniform clusters using soft-merging constraint", logfile.name)
  c(clusters, coex.df) %<-%
    mergeUniformCellsClusters(
      cotan,
      clusters=split.clusters,
      checkers=advanced.GDI.uniformity.checker,
      optimizeForSpeed=if (can.use.torch == TRUE && device=="cuda") TRUE else FALSE,
      deviceStr=device,
      cores=args$jobs,
      saveObj=FALSE,
      outDir=outpath
    )
  cotan <- addClusterization(
    cotan,
    clName="merge",
    override=TRUE,
    clusters=clusters,
    coexDF=coex.df
  )
} else {
  print_info("merging uniform clusters using strong-merging constraint", logfile.name)
  GDI.uniformity.checkers.list <- list(
    advanced.GDI.uniformity.checker,
    shiftCheckerThresholds(advanced.GDI.uniformity.checker, 0.01),
    shiftCheckerThresholds(advanced.GDI.uniformity.checker, 0.03)
  )
  prevCheckRes <- data.frame()
  c(clusters, coex.df) %<-%
    mergeUniformCellsClusters(
      cotan,
      clusters=split.clusters,
      checkers=GDI.uniformity.checkers.list,
      allCheckResults=prevCheckRes,
      optimizeForSpeed=if (can.use.torch == TRUE && device=="cuda") TRUE else FALSE,
      deviceStr=device,
      cores=args$jobs,
      saveObj=FALSE,
      outDir=outpath
    )
  cotan <- addClusterization(
    cotan,
    clName="merge",
    override=TRUE,
    clusters=clusters,
    coexDF=coex.df
  )
}

c(summary.data, summary.plot) %<-%
  clustersSummaryPlot(
    cotan,
    plotTitle="clustering summary"
  )

print_result("cotan summary", logfile.name)
closeAllConnections()
summary.data

print_task(paste0("saving cotan data in ", args$outfile), logfile.name)

saveRDS(
  cotan,
  file=file.path(args$outfile)
)

print_task(paste0("saving clusters related-data in ", args$csv), logfile.name)

write.table(
  data.frame(clusters),
  file.path(args$csv),
  row.names=TRUE,
  col.names=FALSE,
  quote=FALSE,
  sep=","
)

options(parallelly.fork.enable = FALSE)

quit(save="no")
