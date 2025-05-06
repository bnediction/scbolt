## sample ids ##

SRA_CTRL = SRR15305311 SRR15305312 SRR15305313 SRR15305314
SRA_TREATED = SRR15305315 SRR15305316 SRR15305317 SRR15305318

## metadata ##

$(eval METADATA_CTRL := age=adult date=29-09-2020 sample_name=ctrl condition=control)			# Must contains condition
$(eval METADATA_TREATED := age=adult date=29-09-2020 sample_name=treated condition=treated)		# Must contains condition

## preprocessing ##

$(eval MAD_DEVIATION := 3 2)

## annotation ##

$(eval CLUSTER_LABEL_INTEGRATED := 0=Rep 1=Prom1 2=Prom2 3=Gran1 4=Gran2 5=Prom3)		# depends on the marker, signature and goea analysis if not well-characterized

## cellrank ##

INITIAL_STATES_CTRL := 1
TERMINAL_STATES_CTRL := 4
INITIAL_STATES_TREATED := 1
TERMINAL_STATES_TREATED := 4

## center-extremity ##

$(eval CENTER_CTRL := Prom1 Prom2)
$(eval EXTREMITY_CTRL := Rep Prom3)
$(eval CENTER_TREATED := Prom1 Prom2)
$(eval EXTREMITY_TREATED := Rep Gran2)
