#!/usr/bin/bash

NC="\033[0m"
RED="\033[0;31m"
LIGHT_RED="\033[91m"
SIZE=50

title() {
  side_size=$(((${1}-${#2})/2))
  side_str=$(printf "%-${side_size}s" "-")
  echo -e "${RED}${side_str// /-}$2${side_str// /-}${NC}"
}

source ${HOME}/anaconda3/etc/profile.d/conda.sh

### Load 10X data ###

title $SIZE "10X data loading"

echo -e "${LIGHT_RED}> control sample (download)...${NC}"
mkdir -p data/scRNA/raw/ct
wget --quiet --recursive --no-parent -nd --reject "index.html" \
  --directory-prefix=data/scRNA/raw/ct \
  ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5492nnn/GSM5492245/suppl/
mv data/scRNA/raw/ct/*matrix.mtx.gz data/scRNA/raw/ct/matrix.mtx.gz
mv data/scRNA/raw/ct/*genes.tsv.gz data/scRNA/raw/ct/features.tsv.gz
mv data/scRNA/raw/ct/*barcodes.tsv.gz data/scRNA/raw/ct/barcodes.tsv.gz

echo -e "${LIGHT_RED}> treated sample (download)...${NC}"
mkdir -p data/scRNA/raw/ra
wget --quiet --recursive --no-parent -nd --reject "index.html" \
  --directory-prefix=data/scRNA/raw/ra \
  ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5492nnn/GSM5492246/suppl/
mv data/scRNA/raw/ra/*matrix.mtx.gz data/scRNA/raw/ra/matrix.mtx.gz
mv data/scRNA/raw/ra/*genes.tsv.gz data/scRNA/raw/ra/features.tsv.gz
mv data/scRNA/raw/ra/*barcodes.tsv.gz data/scRNA/raw/ra/barcodes.tsv.gz

conda activate preprocess

echo -e "${LIGHT_RED}> control sample (conversion)...${NC}"
python pipeline/load_10X.py -i data/scRNA/raw/ct \
  -o data/scRNA/raw/ct/ct.h5ad \
  -s age=adult,date=29-09-2020,sample_name=ctrl,condition=control

echo -e "${LIGHT_RED}> treated sample (conversion)...${NC}"
python pipeline/load_10X.py -i data/scRNA/raw/ra \
  -o data/scRNA/raw/ra/ra.h5ad \
  -s age=adult,date=29-09-2020,sample_name=ra,condition=treated

### Cell filtering ###

title $SIZE "Cell filtering"

echo -e "${LIGHT_RED}> cycle phase markers (download)...${NC}"
mkdir -p data/public/cycle-phases
wget --quiet -cO data/public/cycle-phases/mouse_cycle_markers.rds https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds

echo -e "${LIGHT_RED}> control sample (filtering)...${NC}"
python pipeline/cell_filtering.py \
  --infile data/scRNA/raw/ct/ct.h5ad \
  --marker data/public/cycle-phases/mouse_cycle_markers.rds \
  --outpath data/scRNA/cell_filtering/ct \
  --mitochondrial_threshold 5 \
  --upper-mad 2 \
  --lower-mad 3 \
  --consistency-mad

echo -e "${LIGHT_RED}> treated sample (filtering)...${NC}"
python pipeline/cell_filtering.py \
  --infile data/scRNA/raw/ra/ra.h5ad \
  --marker data/public/cycle-phases/mouse_cycle_markers.rds \
  --outpath data/scRNA/cell_filtering/ra \
  --mitochondrial_threshold 5 \
  --upper-mad 2 \
  --lower-mad 3 \
  --consistency-mad

### Cell type signatures ###

title $SIZE "Cell type signatures loading"

echo -e "${LIGHT_RED}> signatures (download)...${NC}"
mkdir -p data/public/signatures
wget --quiet -cO data/public/signatures/geiger.xls https://doi.org/10.1371/journal.pbio.2003389.s025 
wget --quiet -cO data/public/signatures/chambers.xls https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls

echo -e "${LIGHT_RED}> signatures (conversion)...${NC}"
python pipeline/load_signatures.py \
  --table-infile data/public/signatures/chambers.xls \
  --list-infile data/public/signatures/geiger.xls \
  --outfile data/public/signatures/signatures.json

### Gene filtering and normalization ###

title $SIZE "Gene filtering and normalization"

echo -e "${LIGHT_RED}> control sample (normalization)...${NC}"
python pipeline/normalization.py \
  --infile data/scRNA/cell_filtering/ct/tables/counts.h5ad \
  --outpath data/scRNA/normalization/ct \
  --correction G2M_score S_score G1_score \
  --min-cell-expression-proportion 0.001 \
  --jobs 6

echo -e "${LIGHT_RED}> treated sample (normalization)...${NC}"
python pipeline/normalization.py \
  --infile data/scRNA/cell_filtering/ra/tables/counts.h5ad \
  --outpath data/scRNA/normalization/ra \
  --correction G2M_score S_score G1_score \
  --min-cell-expression-proportion 0.001 \
  --jobs 6

### Clustering cells and marker analysis ###

title $SIZE "Cell clustering and marker analysis"

echo -e "${LIGHT_RED}> control sample (clustering)...${NC}"
python pipeline/cluster.py \
  --infile data/scRNA/normalization/ct/tables/corrected.h5ad \
  --signatures data/public/signatures/signatures.json \
  --outpath data/scRNA/cluster/ct \
  --prefix ct \
  --k-neighbors 20 \
  --neighborhood-graph knn \
  --dimensions 15 \
  --resolution 0.6 \
  --logfc-threshold 0.25 \
  --verbose

echo -e "${LIGHT_RED}> treated sample (clustering)...${NC}"
python pipeline/cluster.py \
  --infile data/scRNA/normalization/ra/tables/corrected.h5ad \
  --signatures data/public/signatures/signatures.json \
  --outpath data/scRNA/cluster/ra \
  --prefix ra \
  --k-neighbors 20 \
  --neighborhood-graph knn \
  --dimensions 15 \
  --resolution 0.6 \
  --logfc-threshold 0.25 \
  --verbose

### Integration and marker analysis ###

title $SIZE "Integration"

echo -e "${LIGHT_RED}> control + treated samples (integration)...${NC}"
python pipeline/integration.py \
  --i1 data/scRNA/normalizing/ct/tables/corrected.h5ad \
  --i2 data/scRNA/normalizing/ra/tables/corrected.h5ad \
  --outpath data/scRNA/integration \
  --label condition \
  --method bbknn \
  --dim-pca 50 \
  --dim-clustering 15 \
  --dim-integration 3 \
  --hvg \
  --metric euclidean \
  --k-neighbors 20 \
  --resolution 0.37 \
  --add-legend \
  --plot-3d \
  --jobs 6 \
  --seed 10 \
  --verbose

echo -e "${LIGHT_RED}> control + treated samples (cell type analysis)...${NC}"
python pipeline/markers.py \
  --infile data/scRNA/integration/tables/bbknn.h5ad \
  --signatures data/public/signatures/signatures.json \
  --outpath data/scRNA/markers \
  --condition condition \
  --group leiden \
  --logfc-threshold 0.25 \
  --prefix bbknn \
  --verbose

echo -e "${LIGHT_RED}> control + treated samples (rename labels)...${NC}"
python pipeline/cluster_labeling.py \
  --infile data/scRNA/integration/tables/bbknn.h5ad \
  --outfile data/scRNA/integration/tables/bbknn_labels_tmp.h5ad \
  --column leiden \
  --name 0=Unknown 1=Rep 2=Prom1 3=Prom2 4=Gran 5=Prom3 \
  --obsm X_umap

echo -e "${LIGHT_RED}> control + treated samples (plot figure)...${NC}"
python pipeline/plot_figure.py --json fig/umap_labels.json

### STREAM analysis ###

title $SIZE "Stream analysis"

conda deactivate
conda activate stream

echo -e "${LIGHT_RED}> control + treated samples (trajectories)...${NC}"
python pipeline/trajectories.py \
  --infile data/scRNA/integration/tables/bbknn_labels.h5ad \
  --outpath data/scRNA/stream \
  --root 4 \
  --clusters 6 \
  --lambda 0.05 \
  --mu 0.05 \
  --alpha 0.03 \
  --extend-leaf-nodes \
  --extend-mode WeigthedCentroid \
  --extend-parameter 0.8 \
  --add-legend \
  --add-graph \
  --jobs 6 \
  --save-tables \
  --plot-3d

### End workflow

conda deactivate