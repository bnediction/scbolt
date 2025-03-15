## sample ids ##

SRA_CTRL = SRR15305311 SRR15305312 SRR15305313 SRR15305314
SRA_TREATED = SRR15305315 SRR15305316 SRR15305317 SRR15305318

## metadata ##

$(eval METADATA_CTRL := age=adult date=29-09-2020 sample_name=ctrl condition=control)			# Must contains condition
$(eval METADATA_TREATED := age=adult date=29-09-2020 sample_name=treated condition=treated)		# Must contains condition

## cluster labels ##

# $(eval CLUSTER_LABEL_CTRL := 0=Prom1 1=Prom2 2=Trans 3=Rep 4=Prom3 5=Gran)		    # depends on the marker, signature and goea analysis if not well-characterized
# $(eval CLUSTER_LABEL_TREATED := 0=Trans 1=Prom1 2=Unknown 3=Rep 4=Gran 5=Rep)		    # depends on the marker, signature and goea analysis if not well-characterized
$(eval CLUSTER_LABEL_INTEGRATED := 0=Rep 1=Prom1 2=Prom2 3=Gran1 4=Gran2 5=Prom3)		# depends on the marker, signature and goea analysis if not well-characterized

$(eval CENTER_CTRL := Prom1 Prom2)
$(eval EXTREMITY_CTRL := Rep Prom3)
$(eval EXCLUDE_CTRL := true)
$(eval CENTER_TREATED := Prom1 Prom2)
$(eval EXTREMITY_TREATED := Rep Gran2)
$(eval EXCLUDE_TREATED := true)

## others parameters ##

BINARIZATION_ONLY_HVG = false
ZEROES_ARE_ZEROES := true

BOOLEAN_NETWORK_REF = $(PUBLIC)/data/public/reference/APL_model.bnet