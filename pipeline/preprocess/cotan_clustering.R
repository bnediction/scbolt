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
  "torch",
  "Seurat"
)
pkgs.to.install <- pkgs.to.load[!(pkgs.to.load %in% installed.packages()[,"Package"])]

if (length(pkgs.to.install)>0) {
  install.packages(pkgs.to.install)
}
for (pkg in pkgs.to.load) {
  suppressPackageStartupMessages(library(pkg, character.only = TRUE))
}

is.defined = function(x)!is.null(x)

description <- ""
usage <- ""
arguments <- list(
  make_option(c("-i", "--infile"),
              dest="infile",
              type="character",
              default=NULL,
              metavar="FILE",
              help="counting file (csv format)",
              ),
  make_option(c("-o", "--outpath"),
              dest="outpath",
              type="character",
              default=NULL,
              metavar="PATH",
              help="output path"
              ),
  make_option(c("-s", "--sep"),
              dest="sep",
              type="character",
              action="store",
              default="\t",
              metavar="CHAR",
              help="field delimiter for csv infile (default: `\\t`)"
              ),
  make_option(c("-c", "--condition"),
              dest="condition",
              type="character",
              action="store",
              default="control",
              metavar="LITERAL",
              help="sample condition (default: control)"
  ),
  make_option("--drop-mithocondrial",
              dest="drop_mithocondrial",
              action = "store_true",
              default = FALSE,
              help = "drop mithocondrial genes (default: false)"
  ),
  make_option("--min-reads",
              dest="min_reads",
              type="integer",
              action="store",
              default=NULL,
              metavar="INT",
              help="drop cells with too few reads, potentially being dead (default: none)"
  ),
  make_option("--max-reads",
              dest="max_reads",
              type="integer",
              action="store",
              default=NULL,
              metavar="INT",
              help="drop cells with too many reads, potentially being multiplets (default: none)"
  ),
  make_option("--min-expression",
              dest="min_expression",
              type="integer",
              action="store",
              default=NULL,
              metavar="INT",
              help="drop cells with too low gene expression, potentially being dead (default: none)"
  ),
  make_option("--max-expression",
              dest="max_expression",
              type="integer",
              action="store",
              default=NULL,
              metavar="INT",
              help="drop cells with too many gene expression, potentially being multiplets (default: none)"
  ),
  make_option("--mithocondrial-threshold",
              dest="mithocondrial_threshold",
              type="double",
              action="store",
              default=NULL,
              metavar="[0-1]",
              help="drop cells with too high percentage of mithocondrial genes, potentially being dead (default: none)"
  ),
  make_option("--cotan-filtering",
              dest="cotan_filtering",
              action = "store_true",
              default = FALSE,
              help = "drop cell outliers (default: false)"
  ),
  make_option("--min-ude",
              dest="ude_threshold",
              type="double",
              action="store",
              default=NULL,
              metavar="[0-1]",
              help="drop cells with too high percentage of mithocondrial genes, potentially being dead (recommended: 0.3, default: none)"
  ),
  
  make_option(c("-j", "--jobs"),
              dest="jobs",
              type="integer",
              action="store",
              default=1,
              metavar="INT",
              help="number of process to use (default: 1)"
  ),
  make_option("--merge-clusters",
              dest="merge_clusters",
              action = "store_true",
              default = FALSE,
              help = "merge clusters to achieve cluster uniformity (default: false)"
  ),
)

parser <- OptionParser(
  description=description,
  usage=usage,
  option_list=arguments,
  )
args <- parse_args(parser)

args <- c()
args$infile <- "data/rna/ctrl/clustering/clusters/counts.csv"
args$outpath <- "data/rna/ctrl/clustering/clusters/counts.h5ad"
args$sep <- ","
args$cotan_filtering <- TRUE
args$jobs <- 15
args$merge_clusters <- TRUE


print(paste("infile:",args$infile))
print(paste("outpath:",args$outpath))
print(paste("sep:",args$sep))
print(paste("condition:",args$condition))
print(paste("drop mithocondrial:",args$drop_mithocondrial))
print(paste("min_reads:",args$min_reads))
print(paste("max_reads:",args$max_reads))
print(paste("min_expression:",args$min_expression))
print(paste("max_expression:",args$max_expression))
print(paste("mithocondrial_threshold:",args$mithocondrial_threshold))
print(paste("cotan_filtering:",args$cotan_filtering))
print(paste("min_ude:",args$min_ude))
print(paste("jobs:",args$jobs))

if (is.null(args$infile)) {
  stop("`--infile` argument is not specified.")
} else if (is.null(args$outpath)) {
  stop("`--outpath` argument is not specified.")
}

dir.create(
  path=args$outpath,
  showWarnings=FALSE,
  recursive=TRUE
)

setLoggingFile(file.path(args$outpath, "cotan.log"))

cat("Data loading...\n")

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

cat("Data preprocessing...\n")

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
  
  cotan <- addElementToMetaDataset(cotan, "minimum UDE cell threshold", args$ude_threshold)
  cells.to.remove <- getCells(cotan)[getNu(cotan) < args$ude_threshold]
  cotan <- dropGenesCells(cotan, cells = cells.to.remove)
} else {
  cotan <- addElementToMetaDataset(cotan, tag="cotan filtering", value=FALSE)
}

cat("Cotan analysis...\n")

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
  outDir=args$outpath
)

global.differentiation.index <- calculateGDI(cotan)
cotan <- storeGDI(
  cotan,
  genesGDI=global.differentiation.index
)

cat("Cotan clustering...\n")

advanced.GDI.uniformity.checker <- new("AdvancedGDIUniformityCheck")

c(split.clusters, split.coex.df) %<-%
  cellsUniformClustering(
    cotan,
    initialResolution=0.8,
    checker=advanced.GDI.uniformity.checker,
    optimizeForSpeed=if (can.use.torch == TRUE && device=="cuda") TRUE else FALSE,
    deviceStr=device,
    cores=args$jobs,
    saveObj=FALSE,
    outDir=args$outpath
  )
cotan <- addClusterization(
  cotan,
  clName="split",
  clusters=split.clusters,
  coexDF=split.coex.df
)

table(split.clusters)

c(summary.data, summary.plot) %<-%
  clustersSummaryPlot(
    cotan,
    clName="split",
    plotTitle="cluster summary"
  )

summaryData

if (isTRUE(args$merge_clusters)){
  c(clusters, coex.df) %<-%
    mergeUniformCellsClusters(
      cotan,
      clusters=split.clusters,
      checkers=advanced.GDI.uniformity.checker,
      optimizeForSpeed=if (can.use.torch == TRUE && device=="cuda") TRUE else FALSE,
      deviceStr=device,
      cores=args$jobs,
      saveObj=FALSE,
      outDir=args$outpath
    )
  cotan <- addClusterization(
    cotan,
    clName="merge",
    override=TRUE,
    clusters=clusters,
    coexDF=coex.df
  )
} else {
  c(clusters, coex.df) %<-%
    c(split.clusters, split.coex.df)
}

table(clusters)

cat("Umap plotting...\n")

c(umap.plot, cells.pca) %<-%
  cellsUMAPPlot(
    cotan,
    clName="merge",
    dataMethod="LogLikelihood",
    colors=NULL,
    numNeighbors=15L,
    minPointsDist=0.2
  )
plot(umapPlot)

cat("Data saving...\n")

saveRDS(cotan, file = file.path(args$outpath, "cotan.RDS"))

setLoggingFile("")
options(parallelly.fork.enable = FALSE)


### Third iteration

GDI.uniformity.checkers.list <- list(
  advanced.GDI.uniformity.checker,
  shiftCheckerThresholds(advanced.GDI.uniformity.checker, 0.01),
  shiftCheckerThresholds(advChecker, 0.03)
)
prevCheckRes <- data.frame()

c(clusters2, coex.df2) %<-%
  mergeUniformCellsClusters(
    cotan,
    clusters=split.clusters,
    checkers=GDI.uniformity.checkers.list,
    allCheckResults=prevCheckRes,
    optimizeForSpeed=if (can.use.torch == TRUE && device=="cuda") TRUE else FALSE,
    deviceStr=device,
    cores=args$jobs,
    saveObj=FALSE,
    outDir=args$outpath
  )
cotan <- addClusterization(
  cotan,
  clName="merge2",
  override=TRUE,
  clusters=clusters2,
  coexDF=coex.df2
)
table(clusters2)




# quantile.90 <- quantile(unlist(global.differentiation.index[2], use.names=FALSE), probs=0.9)
# genes.list <- row.names(subset(global.differentiation.index, GDI > quantile.90))[0:10]

# plot(genesHeatmapPlot(cotan, primaryMarkers = genes.list,
#                       pValueThreshold = 0.001, symmetric = TRUE))

quit(save="no")
