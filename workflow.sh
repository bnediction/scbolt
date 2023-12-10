### Load 10X data ###

python py_src/load_10X.py -i data/scRNA/raw/ct \
  -o data/scRNA/raw/ct/ct.h5ad \
  -s age=adult,date=29-09-2020,sample_name=ctrl,condition=control

python py_src/load_10X.py -i data/scRNA/raw/ra \
  -o data/scRNA/raw/ra/ra.h5ad \
  -s age=adult,date=29-09-2020,sample_name=ra,condition=treated

### Gene filtering ###

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
