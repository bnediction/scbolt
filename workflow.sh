### Load 10X data ###

python py_src/load_10X.py -i data/scRNA/raw/ct \
  -o data/scRNA/raw/ct/ct.h5ad \
  -s age=adult,date=29-09-2020,sample_name=ctrl,condition=control

python py_src/load_10X.py -i data/scRNA/raw/ra \
  -o data/scRNA/raw/ra/ra.h5ad \
  -s age=adult,date=29-09-2020,sample_name=ra,condition=treated

### Cell filtering ###

mkdir -p data/public/cycle-phases
wget -cO data/public/cycle-phases/mouse_cycle_markers.rds https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds

python py_src/cell_filtering.py \
  --infile data/scRNA/raw/ct/ct.h5ad \
  --marker data/public/cycle-phases/mouse_cycle_markers.rds \
  --outpath data/scRNA/cell_filtering/ct \
  --mitochondrial_threshold 5 \
  --upper-mad 2 \
  --lower-mad 3 \
  --consistency-mad 1

python py_src/cell_filtering.py \
  --infile data/scRNA/raw/ra/ra.h5ad \
  --marker data/public/cycle-phases/mouse_cycle_markers.rds \
  --outpath data/scRNA/cell_filtering/ra \
  --mitochondrial_threshold 5 \
  --upper-mad 2 \
  --lower-mad 3 \
  --consistency-mad 1

### Cell type signature ###

mkdir -p data/public/signatures
wget -cO data/public/signatures/geiger.xls https://doi.org/10.1371/journal.pbio.2003389.s025 
wget -cO data/public/signatures/chambers.xls https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls

### Gene filtering and normalization ###

python py_src/normalization.py \
  --infile data/scRNA/cell_filtering/ct/tables/counts.h5ad \
  --outpath data/scRNA/normalizing/ct \
  --correction G2M_score+S_score+G1_score \
  --min-cell-expression-proportion 0.001 \
  --jobs 6

python py_src/normalization.py \
  --infile data/scRNA/cell_filtering/ra/tables/counts.h5ad \
  --outpath data/scRNA/normalizing/ra \
  --correction G2M_score+S_score+G1_score \
  --min-cell-expression-proportion 0.001 \
  --jobs 6
