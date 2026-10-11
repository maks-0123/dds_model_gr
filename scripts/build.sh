#!/usr/bin/env bash
# =====================================================================================
# DAC nonlinearity tests (AD9081, Table 3 -> Table 16):
#   Verilog -> Verilator (shared lib) -> GNU Radio (dds.grc, File Sink) -> sfdr.py
#
# For every scenario x test point:
#   1. build dds_gr_all.v with the scenario parameters (-G...)
#   2. run dds.grc (it loads the Verilator library and writes $RAW)
#   3. measure the record (sfdr.py)  -> results/results.csv
#   4. compute the same point with the bit-exact Python model -> results/reference.csv
# At the end: report.py -> results/summary.md + plots, and the chain check
# (measured must equal the reference to ~0.01 dB).
#
# Run from scripts/ (as before).  Every path can be overridden from the environment:
#   SRC=... GRC=... RAW=... ./build.sh
#   ONLY="inl3 full" QUICK=1 ./build.sh          # subset of scenarios / test points
# =====================================================================================
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
SRC=${SRC:-$(cd "$HERE/.." && pwd)}          # dds_gr_all.v, wrapper.cpp, dds.grc
MDIR=${MDIR:-$SRC/obj_dir}                   # Verilator output dir (GNU Radio loads the lib from here)
GRC=${GRC:-$SRC/dds.grc}
DTYPE=${DTYPE:-int32}                        # File Sink item size: sizeof_int -> int32
case "$(uname)" in Darwin) LIB_DEF=libdds.dylib ;; *) LIB_DEF=libdds.so ;; esac
LIB=${LIB:-$LIB_DEF}                         # library name expected by the GNU Radio block
RES=${RES:-$HERE/results}

# Python with numpy (conda "python" first; the system python3 on macOS has no numpy)
if [ -z "${PY:-}" ]; then
  for c in python python3; do
    if command -v "$c" >/dev/null && "$c" -c "import numpy, matplotlib, pandas" 2>/dev/null; then PY=$c; break; fi
  done
  [ -n "${PY:-}" ] || { echo "ERROR: no python with numpy+matplotlib+pandas (conda activate ... or PY=/path/to/python)" >&2; exit 1; }
fi

# File Sink path: taken from dds.grc (blocks_file_sink -> file:), or RAW=... from the environment
grc_sink() {
  awk '/id: blocks_file_sink/ {s=1} s && /^ *file:/ {sub(/^ *file: */,""); gsub(/["\047]/,""); print; exit}' "$1"
}
if [ -z "${RAW:-}" ]; then
  RAW=$(grc_sink "$GRC" || true)
  [ -n "$RAW" ] || { echo "ERROR: File Sink path not found in $GRC, set RAW=..." >&2; exit 1; }
  case "$RAW" in /*) ;; *) RAW="$(cd "$(dirname "$GRC")" && pwd)/$RAW" ;; esac
fi
echo "python: $(command -v "$PY") | File Sink: $RAW | lib: $MDIR/$LIB"

# ---- test setup (keep consistent with sfdr.py / model_ref.py) ----
FDAC_MHZ=12000          # fOUT = M / 2^LOG2N * fDAC  (only used to pick M and label plots)
LOG2N=15                # FFT length 32768 = DDS phase resolution in coherent mode
DW=16
FRAC=4                  # DAC output has FRAC fraction bits: full scale 2^(DW-1+FRAC)
AW=16                   # >= LOG2N: no phase truncation (AW=14 -> ~-80 dBc spurs, see scenario aw14)
RW=20
SKIP=1000               # samples dropped at the start of the record
SPACING=2               # two-tone spacing in bins: 2 * 12000/32768 = 0.73 MHz (Table 16: 1 MHz)
BITS=$((DW - 1 + FRAC))

FOUT_1T="70 100 500 900 1900 2600 3700 4500"   # Table 16 SFDR points, MHz
FOUT_2T="1900 2600 3700"                       # Table 16 IMD3 points, MHz
if [ "${QUICK:-0}" = 1 ]; then FOUT_1T="100 900 3700"; FOUT_2T="1900"; fi

#        name | Verilog parameters
SCENARIOS=(
  "ideal|NONLIN=0"
  "aw14|NONLIN=0 AW=14"
  "inl2|NONLIN=1 INL2_Q=128 INL3_Q=0 DNL_Q=0"
  "inl3|NONLIN=1 INL2_Q=0 INL3_Q=128 DNL_Q=0"
  "dnl|NONLIN=1 INL2_Q=0 INL3_Q=0 DNL_Q=56"
  "full|NONLIN=1 INL2_Q=48 INL3_Q=48 DNL_Q=56 SEED=8"
)

# nearest odd M for a frequency in MHz
m_of() { awk -v f="$1" -v n=$((1 << LOG2N)) -v fd="$FDAC_MHZ" 'BEGIN { x = f * n / fd; print 2 * int(x / 2) + 1 }'; }

die() { echo "ERROR: $*" >&2; exit 1; }
[ -f "$SRC/dds_gr_all.v" ] || die "no $SRC/dds_gr_all.v (set SRC=...)"
[ -f "$SRC/wrapper.cpp" ]  || die "no $SRC/wrapper.cpp (set SRC=...)"
[ -f "$GRC" ]              || die "no $GRC (set GRC=...)"
[ -d "$(dirname "$RAW")" ] || die "directory of RAW does not exist: $RAW"
command -v verilator >/dev/null || die "verilator not found"
command -v grcc      >/dev/null || die "grcc not found"

mkdir -p "$RES"/raw "$RES"/meas "$RES"/logs
rm -f "$RES/results.csv" "$RES/reference.csv"

run_point() {   # name params m [m2]
  local name=$1 params=$2 m=$3 m2=${4:-}
  local id="${name}_M${m}${m2:+_M${m2}}"
  local G=(-GSRC=0 -GOUT_SEL=0 -GDW=$DW -GFRAC=$FRAC -GAW=$AW -GRW=$RW -GLOG2N=$LOG2N -GM_CYCLES=$m)
  local t; for t in $params; do G+=("-G$t"); done          # scenario params override the defaults above
  local MEAS=(--m "$m") REFP="AW=$AW $params"
  if [ -n "$m2" ]; then
    G+=(-GTONES=2 -GM_SPACING=$((m2 - m))); MEAS+=(--m2 "$m2")
  else
    G+=(-GTONES=1)
  fi

  echo "=== $id ==="
  verilator --cc --exe --build --top-module dds_gr "${G[@]}" \
    --Mdir "$MDIR" -CFLAGS "-fPIC -O2" -LDFLAGS "-shared" -MAKEFLAGS "-B" \
    -o "$LIB" -Wno-fatal -Wno-lint -Wno-style \
    "$SRC/dds_gr_all.v" "$SRC/wrapper.cpp" > "$RES/logs/build_$id.log" 2>&1 \
    || { tail -20 "$RES/logs/build_$id.log"; die "verilator failed ($id)"; }

  rm -f "$RAW"
  ( cd "$(dirname "$GRC")" && grcc -r "$(basename "$GRC")" ) > "$RES/logs/grc_$id.log" 2>&1 \
    || { tail -20 "$RES/logs/grc_$id.log"; die "GNU Radio run failed ($id)"; }
  if [ ! -s "$RAW" ]; then
    echo "---- GNU Radio log ($RES/logs/grc_$id.log):" >&2; tail -25 "$RES/logs/grc_$id.log" >&2
    echo "---- .bin files written in the last 2 minutes under $SRC:" >&2
    find "$SRC" -name "*.bin" -mmin -2 -not -path "*/results/*" 2>/dev/null | head >&2
    die "$RAW was not written (File Sink path in $GRC, or the flowgraph did not run)"
  fi
  mv "$RAW" "$RES/raw/$id.bin"

  $PY "$HERE/sfdr.py" "$RES/raw/$id.bin" "${MEAS[@]}" --bits $BITS --dtype "$DTYPE" --skip $SKIP \
      --fdac $FDAC_MHZ --csv "$RES/results.csv" --tag "$name" | tee "$RES/meas/$id.txt" | sed -n '1,4p'
  $PY "$HERE/model_ref.py" --params "$REFP" "${MEAS[@]}" --fdac $FDAC_MHZ \
      --csv "$RES/reference.csv" --tag "$name" > "$RES/meas/${id}_ref.txt"
}

for s in "${SCENARIOS[@]}"; do
  name=${s%%|*}; params=${s#*|}
  if [ -n "${ONLY:-}" ] && [[ " $ONLY " != *" $name "* ]]; then continue; fi
  echo "##### scenario $name: $params"
  case "$params" in *NONLIN=1*)
    $PY "$HERE/model_ref.py" --params "$params" --inl-dnl --plot "$RES/inl_dnl_$name.png" \
      | tee "$RES/meas/inl_dnl_$name.txt" ;;
  esac
  for f in $FOUT_1T; do run_point "$name" "$params" "$(m_of "$f")"; done
  for f in $FOUT_2T; do
    m1=$(m_of "$f"); run_point "$name" "$params" "$m1" $((m1 + SPACING))
  done
done

$PY "$HERE/report.py" "$RES"