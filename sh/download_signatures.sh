#!/bin/bash

geiger_url="https://doi.org/10.1371/journal.pbio.2003389.s025"
chambers_url="https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls"

geiger_file="geiger_signatures.xls"
chambers_file="chambers_signatures.xls"
outpath="../data/public"
geiger_path="${outpath}/${geiger_file}"
chambers_path="${outpath}/${chambers_file}"

mkdir -p ${outpath}
wget -cO - ${geiger_url} > ${geiger_path}
wget -cO - ${chambers_url} > ${chambers_path}
