import argparse
import csv
import scipy.io
import pandas as pd
import scanpy as sc
import warnings

from pathlib import Path

warnings.filterwarnings("ignore")

class coordinateListSeqParser(object):

    def __init__(
        self,
        counts:lambda x: Path(x).resolve().as_posix(),
        genes:lambda x: Path(x).resolve().as_posix(),
        barcodes:lambda x: Path(x).resolve().as_posix(),
        out=Path("out.txt")
        ):
        """coordinateListSeqParser: Parser and converter of Rna-Seq data compressed in the COO (coordinate list) format.\n
        Reader of both .mtx counting file, gene name file and barcode file.
        COO format consists of compressed reordered sparse data.\n"""

        self._output = Path(out).resolve().as_posix()
        self.transcript_ids = list()
        self.gene_names = list()
        self.feature_types = list()
        self.barcodes = list()
        self.counts = scipy.io.mmread(counts)

        with open(genes, newline='') as f:
            for row in csv.reader(f, delimiter='\t'):
                self.transcript_ids.append(row[0]); self.gene_names.append(row[1]); self.feature_types.append(row[2])

        with open(barcodes, newline='') as f:
            self.barcodes = [row[0] for row in csv.reader(f, delimiter='\t')]
    
    def to_anndata(self, gene_barcode=True):
        """Return an AnnData object corresponding to gene-barcode RNA-seq matrix."""
        
        genes_df = pd.DataFrame({
            'transcript_id':self.transcript_ids,
            'gene_name':self.gene_names,
            'feature_type':self.feature_types
        })
        barcodes_df = pd.DataFrame({'barcodes':self.barcodes})

        if gene_barcode:
            counting_matrix = sc.AnnData(
                X=self.counts,
                obs=genes_df,
                var=barcodes_df
            )
        else:
            counting_matrix = sc.AnnData(
                X=self.counts.T,
                obs=barcodes_df,
                var=genes_df
            )

        return counting_matrix

    def to_df(self, gene_label='gene_name'):
        """Return a Pandas DataFrame object corresponding to gene-barcode RNA-seq matrix."""

        counting_matrix = pd.DataFrame.sparse.from_spmatrix(self.counts)
        counting_matrix.columns = self.barcodes
        match gene_label:
            case 'transcript_id':
                counting_matrix.insert(loc=0, column='gene', value=self.transcript_ids)
            case 'gene_name':
                counting_matrix.insert(loc=0, column='gene', value=self.gene_names)
            case _:
                raise ValueError("gene_label is not equal to 'transcript_id' or 'gene_name', aborting")
        
        return counting_matrix

    def to_csv(self, outpath=None, sep=",", index=False):
        """Uncompressed Rna-Seq data and save it into a specific filename.\n
        By default, save into the outpath attribute"""

        _out = outpath if not None else self._output
        
        if Path(_out).resolve().exists():
            # avoid overwritting existing config files
            raise FileExistsError("Uncompressed counting file already exists, aborting")
        elif not (self.transcript_ids and self.gene_names and self.feature_types):
            # do not decompressed data not yet load. Please use run() method.
            raise ValueError("Data not yet load, aborting")
        
        self.to_df().to_csv(_out, sep=sep, index=index)

class coordinateListSeqCLIParser(coordinateListSeqParser):

    def __init__(self):
        parser = argparse.ArgumentParser(
            prog="multiplexSeqCLIParser",
            description="""coordinateListSeqParser: CLI parser on Rna-Seq data compressed in the COO (coordinate list) format.\n
            Reader of both .mtx counting file, gene name file and barcode file.
            COO format consists of compressed reordered sparse data.\n""",
            usage="python rnaSeqDemultiplexing.py counts genes barcodes [<args>]")

        parser.add_argument(
            dest="counts_path",
            metavar="counts",
            type=lambda x: Path(x).resolve(),
            help="mtx compressed counting file path"
        )

        parser.add_argument(
            dest="features_path",
            metavar="genes",
            type=lambda x: Path(x).resolve(),
            help="[tsv|csv|txt] gene name file path"
        )

        parser.add_argument(
            dest="barcodes_path",
            metavar="barcodes",
            type=lambda x: Path(x).resolve(),
            help="[tsv|csv|txt] barcode file path"
        )

        parser.add_argument(
            "-o", "--output",
            type=lambda x: Path(x).resolve(),
            dest="out",
            default=None,
            help="mtx demultiplexed counting file path"
        )

        args = parser.parse_args()

        if args.out is None:
            super().__init__(args.counts_path, args.features_path, args.barcodes_path)
        else:
            super().__init__(args.counts_path, args.features_path, args.barcodes_path, out=args.out)

def to_xcsv(metadata_path, labels, *seqParsers, gene_barcode=True):
    """Uncompress multiple Rna-Seq data and generate a metadata file on barcodes.
    Then, save them into csv format.\n
    """

    if not isinstance(metadata_path, Path):
        raise TypeError("metadata_path arg must be a Path object, aborting")

    for seqParser in seqParsers:
        if not isinstance(seqParser, (coordinateListSeqParser, coordinateListSeqCLIParser)):
            raise TypeError("seqParsers must be coordinateListSeqParser or coordinateListSeqCLIParser objects, aborting")
    
    barcodes_ls = list(); labels_ls = list()
    metadata_df = pd.DataFrame(columns=['barcode', 'label'])

    for idx, seqParser in enumerate(seqParsers):
        counts_df = seqParser.to_df()
        if gene_barcode:
            counts_df.to_csv(seqParser._output, sep=",", index=False)
        else:
            counts_df.set_index('gene').transpose().to_csv(seqParser._output, sep=",", index=True)
        barcodes_ls.extend(seqParser.barcodes)
        labels_ls.extend([labels[idx]]*(len(counts_df.columns)-1))
    
    metadata_df['barcode'] = barcodes_ls
    metadata_df['label'] = labels_ls
    metadata_df.to_csv(metadata_path, sep=",", index=False)

def to_hdf5(labels, *seqParsers, gene_barcode=True, out="out.h5ad"):
    """Uncompress and merge multiple Rna-Seq data and generate a serialized object.
    Then, save it into hdf5 format.\n"""

    for seqParser in seqParsers:
        if not isinstance(seqParser, (coordinateListSeqParser, coordinateListSeqCLIParser)):
            raise TypeError("seqParsers must be coordinateListSeqParser or coordinateListSeqCLIParser objects, aborting")
    
    adatas = dict()

    for i, seqParser in enumerate(seqParsers):
        adatas[labels[i]] = seqParser.to_anndata()
        if i==0:
            obs = adatas[labels[i]].obs
        elif not obs.equals(adatas[labels[i]].obs):
            raise ValueError("Gene names are different or not ordered between seqParsers, aborting")

    adata = sc.concat(adatas, join="outer", label="label", axis=1)
    adata.obs_names_make_unique(); adata.var_names_make_unique()
    adata.obs = obs

    if not gene_barcode:
        adata = adata.transpose()

    adata.write_h5ad(filename=out, compression="gzip")
