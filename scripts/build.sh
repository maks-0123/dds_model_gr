#!/usr/bin/env bash
# Sweep AW x DW x M: build the Verilator model, run the GNU Radio flowgraph, measure SFDR.
# Run from the scripts/ directory.
set -euo pipefail

SRC=/Users/maksimromanuta/Documents/work_on_etalon/icarus_DDS.worktrees/gnu-dds-all-v
MDIR=/Users/maksimromanuta/Documents/work_on_etalon/icarus_DDS.worktrees/gnu-dds-all-v/obj_dir
RAW=/Users/maksimromanuta/Documents/work_on_etalon/icarus_DDS.worktrees/gnu-dds-all-v/scripts/f32_IMD3.bin
                            # MUST be the same path as in the File Sink block of dds.grc
DTYPE=int32                 # File Sink item size: sizeof_int -> int32, sizeof_float -> float32
RES=results
RW=20                       # constant reference width, RW >= max(DW) + 4
AWS="10, 12, 14, 16"
DWS="10, 12, 14, 16"
MS="2453, 2455, 2457, 2459, 2461"   # odd values, averaged for every (AW, DW)

mkdir -p "$RES"
[ -d "$(dirname "$RAW")" ] || { echo "Directory of RAW does not exist: $RAW"; exit 1; }

for AW in $AWS; do
  for DW in $DWS; do
    for M in $MS; do

      echo "=== AW=$AW DW=$DW M=$M ==="
      verilator --cc --exe --build \
        --top-module dds_gr -GTEST_MODE=0 -GOUT_SEL=0 \
        -GAW=$AW -GDW=$DW -GRW=$RW \
        --Mdir "$MDIR" \
        -CFLAGS "-fPIC" -LDFLAGS "-shared" -MAKEFLAGS "-B" \
        -o libdds.dylib -Wno-fatal \
        "$SRC/dds_gr_all.v" "$SRC/wrapper.cpp"

      rm -f "$RAW"
      ( cd .. && grcc -r dds.grc )
      mv "$RAW" "$RES/f_AW${AW}_DW${DW}_M${M}.bin"
    done

    echo "--- AW=$AW DW=$DW ---" | tee -a "$RES/summary.txt"
    python sfdr.py "$RES"/f_AW${AW}_DW${DW}_M${M}.bin --dw "$DW" --dtype "$DTYPE" | tee -a "$RES/summary.txt"
  done
done