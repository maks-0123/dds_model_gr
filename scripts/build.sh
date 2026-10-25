#!/usr/bin/env bash
# =====================================================================================
# DAC nonlinearity / jitter / shuffle tests (AD9081, Table 3 -> Table 16):
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
#   ONLY="inl3 full" QUICK=1 ./build.sh                  # subset of scenarios / test points
#   ONLY="ideal jit25 jit50 jit100 jit200 full_jit50" ./build.sh   # jitter study only
#   ONLY="full shuf_rot shuf_dwa" ./build.sh             # shuffle study (Table 16: shuffle enabled)
#   KEEP=1 ONLY="shuf_rot" ./build.sh                    # do not wipe results.csv / reference.csv
#   SEEDSTUDY=1 ./build.sh                               # 20 SEEDs x {full, shuf_rot, shuf_dwa}, Python model only
#   SEEDSTUDY=1 PYONLY=0 ./build.sh                      # the same through Verilator + GNU Radio
#   PIPE=7 DELAY=4 ./build.sh                            # alignment of the SHUF reference (find_pipe.py)
#   REMEASURE=1 ./build.sh                               # rebuild results.csv / reference.csv from
#                                                        # the records already in results/raw (no Verilator, no GNU Radio)
#
# SHUF needs `parameter integer SHUF` in the dds_gr top and `.SHUF(SHUF)` on dac_nonlin.
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
PIPE=${PIPE:-7}                              # shuffle generator clocks before DDS sample 0 (find_pipe.py)
DELAY=${DELAY:-4}                            # record alignment raw[SKIP+i] = model[SKIP+i-DELAY]
                                             # (both only matter for the bit-exact SHUF=1/2 reference)

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
JIT_FS=0                # default clock jitter, fs rms. Keep 0: jitter is set per scenario below

FOUT_1T="70 100 500 900 1900 2600 3700 4500"   # Table 16 SFDR points, MHz
FOUT_2T="1900 2600 3700"                       # Table 16 IMD3 points, MHz
if [ "${QUICK:-0}" = 1 ]; then FOUT_1T="100 900 3700"; FOUT_2T="1900"; fi

# Datasheet context for the scenarios below:
#   Table 3  : INL 8 / DNL 3.5 LSB are specified with shuffling DISABLED  -> full, dnl (SHUF=0)
#   Table 16 : SFDR and IMD3 are measured with shuffle ENABLED            -> shuf_rot, shuf_dwa
#   Table 16 : NSD is measured with shuffle OFF (0 dBFS)                  -> *_jit58 without SHUF
#   Fig. 30  : NSD, shuffle off vs on                                     -> full_jit58 vs shuf_*_jit58
#   sigma = 58 fs : jitter fitted to Table 16 NSD (stage 2 report)
FULL="NONLIN=1 INL2_Q=48 INL3_Q=48 DNL_Q=56 SEED=8"

# ---- stage 1: dynamic (slew-dependent) nonlinearity, dac_dyn ----
# Coefficients fitted to Table 16 by fit_dyn.py (results/dyn_fit.json): five slew terms
# (A..E, they grow with fOUT) plus the memoryless distortion of the analog output stage
# (P2, P3, flat in frequency).  P2/P3 are needed because every slew term dies out at low fOUT
# and cannot produce the 80 dBc that Table 16 shows at 70 MHz; the INL of Table 3 is kept.
DYN=${DYN:-"DYN_A_Q=20 DYN_B_Q=-6 DYN_C_Q=167 DYN_D_Q=-48 DYN_E_Q=-80 DYN_P2_Q=-29 DYN_P3_Q=-178"}
FULLD="$FULL $DYN"                             # Table 3 DAC + fitted dynamics
NOISE_Q=${NOISE_Q:-115}                        # thermal floor -168 dBc/Hz at 0 dBFS

#        name | Verilog parameters
SCENARIOS=(
  "ideal|NONLIN=0"
  "aw14|NONLIN=0 AW=14"
  "inl2|NONLIN=1 INL2_Q=128 INL3_Q=0 DNL_Q=0"
  "inl3|NONLIN=1 INL2_Q=0 INL3_Q=128 DNL_Q=0"
  "dnl|NONLIN=1 INL2_Q=0 INL3_Q=0 DNL_Q=56"
  "full|$FULL"
  # clock jitter (dac_jitter): ideal DAC + white Gaussian jitter of JIT_FS fs rms
  "jit25|NONLIN=0 JIT_FS=25"
  "jit50|NONLIN=0 JIT_FS=50"
  "jit100|NONLIN=0 JIT_FS=100"
  "jit200|NONLIN=0 JIT_FS=200"
  # "real AD9081", shuffle off: static nonlinearity of Table 3 + 50 fs jitter
  "full_jit50|$FULL JIT_FS=50"
  # ---- shuffle (stage 1): same DAC as "full", SHUF=1 random rotation, SHUF=2 DWA ----
  "shuf_rot|$FULL SHUF=1"
  "shuf_dwa|$FULL SHUF=2"
  # ---- shuffle off vs on with the jitter fitted to Table 16 (NSD, Fig. 30) ----
  "full_jit58|$FULL JIT_FS=58"
  "shuf_rot_jit58|$FULL SHUF=1 JIT_FS=58"
  "shuf_dwa_jit58|$FULL SHUF=2 JIT_FS=58"
  # ---- stage 1: dynamic nonlinearity ----
  "dyn|$FULLD"                                   # slew terms only, shuffle off
  "shuf_rot_dyn|$FULLD SHUF=1"                   # Table 16 conditions: shuffle on + dynamics
  # complete AD9081 model: static + shuffle + dynamics + 58 fs jitter + thermal floor
  "ad9081|$FULLD SHUF=1 JIT_FS=58 NOISE_Q=$NOISE_Q"
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
# a bare SEEDSTUDY=1 run touches only seeds.csv, so it must not wipe the main results
if [ "${KEEP:-0}" != 1 ] && ! { [ "${SEEDSTUDY:-0}" = 1 ] && [ -z "${ONLY:-}" ]; }; then
  rm -f "$RES/results.csv" "$RES/reference.csv"
fi

# where run_point appends its results (the seed study switches these)
MCSV="$RES/results.csv"
RCSV="$RES/reference.csv"

run_point() {   # name params m [m2]
  local name=$1 params=$2 m=$3 m2=${4:-}
  local id="${name}_M${m}${m2:+_M${m2}}"
  local G=(-GSRC=0 -GOUT_SEL=0 -GDW=$DW -GFRAC=$FRAC -GAW=$AW -GRW=$RW -GLOG2N=$LOG2N -GM_CYCLES=$m -GJIT_FS=$JIT_FS)
  local t; for t in $params; do G+=("-G$t"); done          # scenario params override the defaults above
  local MEAS=(--m "$m") REFP="AW=$AW $params PIPE=$PIPE DELAY=$DELAY"
  if [ -n "$m2" ]; then
    G+=(-GTONES=2 -GM_SPACING=$((m2 - m))); MEAS+=(--m2 "$m2")
  else
    G+=(-GTONES=1)
  fi

  echo "=== $id ==="
  if [ "${REMEASURE:-0}" = 1 ]; then                      # re-measure an existing record only
    [ -s "$RES/raw/$id.bin" ] || { echo "  no $RES/raw/$id.bin, skipped"; return 0; }
  else
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
  fi

  $PY "$HERE/sfdr.py" "$RES/raw/$id.bin" "${MEAS[@]}" --bits $BITS --dtype "$DTYPE" --skip $SKIP \
      --fdac $FDAC_MHZ --csv "$MCSV" --tag "$name" | tee "$RES/meas/$id.txt" | sed -n '1,4p'
  # bit-exact reference: only without jitter (model_ref.py has no jitter model)
  case "$params" in *JIT_FS=*|*NOISE_Q=*) ;; *)
    $PY "$HERE/model_ref.py" --params "$REFP" "${MEAS[@]}" --fdac $FDAC_MHZ \
        --csv "$RCSV" --tag "$name" > "$RES/meas/${id}_ref.txt" ;;
  esac
}

check_shuf() {   # the Verilog top must pass SHUF down to dac_nonlin
  grep -q '\.SHUF(' "$SRC/dds_gr_all.v" \
    || die "scenario uses SHUF, but dds_gr_all.v has no .SHUF(SHUF) connection: add 'parameter integer SHUF = 0' to dds_gr and '.SHUF(SHUF)' to the dac_nonlin instance"
}

# ---------------- main scenarios ----------------
for s in "${SCENARIOS[@]}"; do
  name=${s%%|*}; params=${s#*|}
  if [ -n "${ONLY:-}" ] && [[ " $ONLY " != *" $name "* ]]; then continue; fi
  if [ "${SEEDSTUDY:-0}" = 1 ] && [ -z "${ONLY:-}" ]; then continue; fi   # SEEDSTUDY alone: seeds only
  echo "##### scenario $name: $params"
  case "$params" in *JIT_FS=*|*NOISE_Q=*) jit=1 ;; *) jit=0 ;; esac
  case "$params" in *SHUF=*) shuf=1; check_shuf ;; *) shuf=0 ;; esac
  # INL/DNL of the static curve (shuffle has no static curve; jitter has no reference)
  if [[ "$params" == *NONLIN=1* ]] && [ $jit = 0 ] && [ $shuf = 0 ]; then
    $PY "$HERE/model_ref.py" --params "$params" --inl-dnl --plot "$RES/inl_dnl_$name.png" \
      | tee "$RES/meas/inl_dnl_$name.txt"
  fi
  for f in $FOUT_1T; do run_point "$name" "$params" "$(m_of "$f")"; done
  # jitter-only scenarios are measured as SNR on one tone; the full chip model also needs IMD3
  if [ $jit = 1 ] && [ "$name" != ad9081 ]; then continue; fi
  for f in $FOUT_2T; do
    m1=$(m_of "$f"); run_point "$name" "$params" "$m1" $((m1 + SPACING))
  done
done

# ---------------- seed study: one SEED = one chip from the batch (report section 5.3) ----------------
# 900 MHz single tone + 1900 MHz two tones, SEED = 1..20, shuffle off / random rotation / DWA.
# Results go to results/seeds.csv and results/seeds_ref.csv (tags full_s<N>, shuf_rot_s<N>, shuf_dwa_s<N>).
# PYONLY=1 (default): the points are computed by the bit-exact Python model only (no Verilator, no GNU Radio,
#   no windows). Valid because the chain check of the same scenarios (full, shuf_rot, shuf_dwa) is 0.000 dB.
#   The model is written to seeds.csv; seeds_ref.csv is not needed.
# PYONLY=0: every point goes through Verilator + GNU Radio (needs a flowgraph that stops by itself).
ref_point() {   # name params m [m2]  -> model_ref.py only
  local name=$1 params=$2 m=$3 m2=${4:-}
  local MEAS=(--m "$m") REFP="AW=$AW $params PIPE=$PIPE DELAY=$DELAY"
  [ -n "$m2" ] && MEAS+=(--m2 "$m2")
  echo "=== ${name}_M${m}${m2:+_M${m2}} (python) ==="
  $PY "$HERE/model_ref.py" --params "$REFP" "${MEAS[@]}" --fdac $FDAC_MHZ \
      --csv "$MCSV" --tag "$name" > "$RES/meas/${name}_M${m}${m2:+_M${m2}}_ref.txt"
}
if [ "${SEEDSTUDY:-0}" = 1 ]; then
  PYONLY=${PYONLY:-1}
  [ "$PYONLY" = 1 ] || check_shuf
  MCSV="$RES/seeds.csv"; RCSV="$RES/seeds_ref.csv"
  rm -f "$MCSV" "$RCSV"
  for seed in $(seq 1 "${NSEEDS:-20}"); do
    for mode in "full:0:" "shuf_rot:1:" "shuf_dwa:2:" "shuf_rot_dyn:1:$DYN"; do
      nm=${mode%%:*}; rest=${mode#*:}; sh=${rest%%:*}; dyn=${rest#*:}
      params="NONLIN=1 INL2_Q=48 INL3_Q=48 DNL_Q=56 SEED=$seed SHUF=$sh $dyn"
      echo "##### seed study $nm seed $seed"
      m1=$(m_of 1900)
      if [ "$PYONLY" = 1 ]; then
        ref_point "${nm}_s${seed}" "$params" "$(m_of 900)"
        ref_point "${nm}_s${seed}" "$params" "$m1" $((m1 + SPACING))
      else
        run_point "${nm}_s${seed}" "$params" "$(m_of 900)"
        run_point "${nm}_s${seed}" "$params" "$m1" $((m1 + SPACING))
      fi
    done
  done
  MCSV="$RES/results.csv"; RCSV="$RES/reference.csv"
fi

if [ -s "$RES/results.csv" ]; then $PY "$HERE/report.py" "$RES"; fi