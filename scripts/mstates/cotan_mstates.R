#!/usr/bin/Rscript

options(
  needs.promptUser=FALSE,
  parallelly.fork.enable=TRUE
)

required.packages <- c(
  "optparse",
  "COTAN",
  "zeallot"
)
missing.packages <- required.packages[
  !vapply(required.packages, requireNamespace, logical(1), quietly = TRUE)
]

if (length(missing.packages) > 0L) {
  stop(
    paste0(
      "missing required R packages: ",
      paste(missing.packages, collapse = ", "),
      ". Reinstall or update the scbolt-cotan conda environment."
    ),
    call. = FALSE
  )
}

for (pkg in required.packages) {
  suppressPackageStartupMessages(library(pkg, character.only = TRUE))
}

datetime.now.POSIXct <- function()
  format(Sys.time(), format = "%Y-%m-%d %H:%M:%S")

print_log <- function(level, msg) {
  cat(paste0(datetime.now.POSIXct(), " - ", level, " - ", msg, "\n"))
}

print_task <- function(msg) {
  print_log("TASK", msg)
}

print_result <- function(msg) {
  print_log("RESULT", msg)
}

print_info <- function(msg) {
  print_log("INFO", msg)
}

print_debug <- function(msg) {
  print_log("DEBUG", msg)
}

print_warning <- function(msg) {
  print_log("WARNING", msg)
}

close_sinks <- function() {
  while (sink.number(type = "message") > 0L) {
    sink(type = "message")
  }
  while (sink.number(type = "output") > 0L) {
    sink(type = "output")
  }
}

is.defined <- function(x)
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
              help="output file storing COTAN object (format: RDS, required)"
              ),
  make_option("--csv",
              dest="csv",
              type="character",
              default=NULL,
              metavar="FILE",
              help="output file storing COTAN macrostates (format: csv)"
  ),
  make_option("--sep",
              dest="sep",
              type="character",
              action="store",
              default="\t",
              metavar="CHAR",
              help="field delimiter for input CSV file (default: `\\t`)"
              ),
  make_option("--name",
              dest="name",
              type="character",
              action="store",
              default="reference",
              metavar="LITERAL",
              help="dataset name (default: reference)"
  ),
  make_option("--drop-mitochondrial",
              dest="drop_mitochondrial",
              action="store_true",
              default=FALSE,
              help="drop mitochondrial genes (default: false)"
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
  make_option("--mitochondrial-threshold",
              dest="mitochondrial_threshold",
              type="double",
              action="store",
              default=NULL,
              metavar="[0-1]",
              help="maximum proportion of mitochondrial gene expression required for a cell to pass filtering, potentially being dead (default: none)"
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
              metavar="[classic | soft-merging | strong-merging]",
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

valid.methods <- c("classic", "soft-merging", "strong-merging")

if (is.null(args$infile)) {
  stop("option --infile required but not specified")
} else if (is.null(args$outfile)) {
  stop("option --outfile required but not specified")
} else if (is.null(args$csv)) {
  stop("option --csv required but not specified")
} else if (!(args$method %in% valid.methods)){
  stop(
    paste0(
      "invalid value for --method: ",
      args$method,
      " (supported values: ",
      paste(valid.methods, collapse = ", "),
      ")"
    )
  )
} else if (isTRUE(args$cotan_filtering) && is.null(args$min_ude)) {
  stop("option --min-ude is required when --cotan-filtering is enabled")
}

outpath <- dirname(args$outfile)
dir.create(
  path=outpath,
  showWarnings=FALSE,
  recursive=TRUE
)
logfile.name <- file.path(outpath, "cotan.log")
invisible(file.create(logfile.name))
logfile.message <- file(logfile.name, open = "a")

sink(logfile.name, append = TRUE, split = TRUE)
sink(logfile.message, type = "message")
on.exit(
  {
    close_sinks()
    if (isOpen(logfile.message)) {
      close(logfile.message)
    }
    options(parallelly.fork.enable = FALSE)
  },
  add = TRUE
)

print_debug(paste0("storing COTAN logs (file=", logfile.name, ")"))
print_task(paste0("loading count matrix (file=", args$infile, ")"))

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
  sampleCondition = args$name
)

print_task("preprocessing count matrix")

if (isTRUE(args$drop_mitochondrial)){
  cotan <- addElementToMetaDataset(cotan, tag="remove mitochondrial genes and cells", value=TRUE)
  genes.to.remove <- getGenes(cotan)[grep("^Mt", getGenes(cotan))]
  cells.to.remove <- getCells(cotan)[which(getCellsSize(cotan) == 0L)]
  cotan <- dropGenesCells(cotan, genes.to.remove, cells.to.remove)
} else {
  cotan <- addElementToMetaDataset(cotan, tag="remove mitochondrial genes and cells", value=FALSE)
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

if (is.defined(args$mitochondrial_threshold)){
  cotan <- addElementToMetaDataset(cotan, "mitochondrial percentage threshold", args$mitochondrial_threshold)
  c(mitochondrial.plot, mitochondrial.sizes) %<-% mitochondrialPercentagePlot(cotan, genePrefix = "^Mt")
  cells.to.remove <- rownames(mitochondrial.sizes)[mitochondrial.sizes[["mit.percentage"]] > args$mitochondrial_threshold]
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

print_task("initializing COTAN settings")

cotan <- clean(cotan)
c(pca.plot, pca.data, genes.plot, UDE.plot, nu.plot, zoomed.nu.plot) %<-% cleanPlots(cotan)

c(can.use.torch, device) %<-% COTAN:::canUseTorch(TRUE, "cuda")
optimize.for.speed <- isTRUE(can.use.torch) && device == "cuda"

cotan <- proceedToCoex(
  cotan,
  calcCoex=TRUE,
  optimizeForSpeed=optimize.for.speed,
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

print_task(paste0("clustering cells (method=COTAN, merging=", args$method, ")"))

advanced.GDI.uniformity.checker <- new("AdvancedGDIUniformityCheck")

print_info("searching uniform clusters")
print_warning("this may take some time.")

c(split.clusters, split.coex.df) %<-%
  cellsUniformClustering(
    cotan,
    initialResolution=0.8,
    maxIterations=args$max_iterations,
    checker=advanced.GDI.uniformity.checker,
    optimizeForSpeed=optimize.for.speed,
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
  print_info("merging uniform clusters (method=soft)")
  c(clusters, coex.df) %<-%
    mergeUniformCellsClusters(
      cotan,
      clusters=split.clusters,
      checkers=advanced.GDI.uniformity.checker,
      optimizeForSpeed=optimize.for.speed,
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
  print_info("merging uniform clusters (method=strong)")
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
      optimizeForSpeed=optimize.for.speed,
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

print_result("COTAN summary")
print(summary.data)

print_task(paste0("saving COTAN object (file=", args$outfile, ")"))

saveRDS(
  cotan,
  file=file.path(args$outfile)
)

print_task(paste0("saving COTAN macrostates (file=", args$csv, ")"))

write.table(
  data.frame(macrostate = clusters),
  file.path(args$csv),
  row.names=TRUE,
  col.names=NA,
  quote=FALSE,
  sep=","
)
