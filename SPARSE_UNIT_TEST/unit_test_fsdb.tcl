dump -file cgra.fsdb -type FSDB
dump -add fiber_glb_tb -fsdb_opt +mda+packedmda+struct
power fiber_glb_tb.dut
power -enable
run
power -disable
run
exit