python py_src/load_10X.py -i data/scRNA/raw/ct \
  -o data/scRNA/raw/ct/ct.h5ad \
  -s age=adult,date=29-09-2020,sample_name=ctrl,condition=control

python py_src/load_10X.py -i data/scRNA/raw/ra \
  -o data/scRNA/raw/ra/ra.h5ad \
  -s age=adult,date=29-09-2020,sample_name=ra,condition=treated

