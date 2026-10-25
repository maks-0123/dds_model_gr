#!/usr/bin/env python3
"""
Bit-exact Python reference of dds_gr_all.v (DDS + dac_nonlin).
 
Uses:
  1) INL/DNL of the configured DAC transfer curve (what the Verilog model really implements):
       python3 model_ref.py --params "NONLIN=1 INL2_Q=64 INL3_Q=64 DNL_Q=56" --inl-dnl [--plot inl.png]
  2) Expected metrics for a test point (reference for the GNU Radio / Verilator run):
       python3 model_ref.py --params "NONLIN=1" --m 2457 [--m2 2459] [--csv results.csv --tag ref:full]
  3) Write the expected output record (to diff against the File Sink output):
       python3 model_ref.py --params "NONLIN=1" --m 2457 --write ref.bin
 
Parameters use the same names and defaults as the Verilog top (dds_gr).
SHUF: 0 = off, 1 = random rotation, 2 = DWA.
PIPE:  clocks the shuffle generator (lcg_r / ptr) has run before DDS sample 0 reaches dac_nonlin.
DELAY: record alignment, raw[SKIP+i] = model[SKIP+i-DELAY].
       Both matter only for the bit-exact match with SHUF=1/2 (found with find_pipe.py:
       PIPE=7, DELAY=4, 100 % equal samples). With SHUF=0 the coherent tone makes any shift
       give the same spectrum.
"""
import argparse
import os
import sys
 
import numpy as np
 
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfdr  # noqa: E402
 
DEFAULTS = dict(SRC=0, TONES=1, NONLIN=0, OUT_SEL=0, DW=16, AW=16, RW=20, FRAC=4, LOG2N=15,
                M_CYCLES=2457, M_SPACING=2, AM_1T=29274, AM_2T=32768,
                INL2_Q=48, INL3_Q=48, DNL_Q=56, SEG_BITS=6, SEED=8,
                SHUF=0, PIPE=7, DELAY=4,
                DYN_A_Q=0, DYN_B_Q=0, DYN_C_Q=0, DYN_D_Q=0, DYN_E_Q=0, DYN_P2_Q=0, DYN_P3_Q=0,
                FDAC_MHZ=12000)
 
 
def parse_params(s):
    p = dict(DEFAULTS)
    for tok in (s or "").split():
        k, v = tok.split("=")
        if k not in p:
            raise SystemExit(f"unknown parameter {k}")
        p[k] = int(v, 0)
    return p
 
 
def _tdiv(a, b):
    """Verilog integer division (truncation toward zero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q
 
 
# ---------------- DDS ----------------
def dds_tone(p, ftw, am, n):
    N, AW, RW = 48, p["AW"], p["RW"]
    k = np.arange(n, dtype=object)                       # exact 48-bit phase
    phase = np.array([(int(i) * ftw) % (1 << N) for i in k], dtype=np.int64)
    addr = (phase >> (N - 16)) >> (16 - AW)
    i = np.arange(1 << AW)
    rom = np.floor(np.sin(2.0 * np.pi * i / (1 << AW)) * ((1 << (RW - 1)) - 1) + 0.5).astype(np.int64)
    return (rom[addr] * am) >> 16                       # prod[RW+15:16]
 
 
def dds_codes(p, m1, n):
    N, DW, RW = 48, p["DW"], p["RW"]
    ftw1 = m1 << (N - p["LOG2N"])
    am = p["AM_2T"] if p["TONES"] == 2 else p["AM_1T"]
    t = dds_tone(p, ftw1, am, n)
    if p["TONES"] == 2:
        t = t + dds_tone(p, ftw1 + (p["M_SPACING"] << (N - p["LOG2N"])), am, n)
    sh = RW - DW
    q = (t + ((1 << (sh - 1)) if sh > 0 else 0)) >> sh
    return np.clip(q, -(1 << (DW - 1)), (1 << (DW - 1)) - 1)
 
 
# ---------------- DAC ----------------
def seg_table(p):
    """eseg[0..NSEG]: eseg[s] = dk[0] + ... + dk[s-1]."""
    nseg = 1 << p["SEG_BITS"]
    lcg, dk = p["SEED"] & 0xFFFFFFFF, []
    for _ in range(nseg):
        acc = 0
        for _ in range(12):
            lcg = (lcg * 1664525 + 1013904223) & 0xFFFFFFFF
            acc += lcg >> 20
        dk.append(acc - 12 * 2048)
    mean = _tdiv(sum(dk), nseg)
    dk = [d - mean for d in dk]
    mx = max(1, max(abs(d) for d in dk))
    dk = [_tdiv(d * p["DNL_Q"], mx) for d in dk]
    return np.concatenate([[0], np.cumsum(dk)]).astype(np.int64)
 
 
def shuffle_es(p, seg):
    """Segment error for SHUF=1 (random rotation) or SHUF=2 (DWA), clock by clock as in Verilog.
 
    ON segments: p0, p0+1, ..., p0+seg-1 (mod NSEG).
    ES = eseg[q] - eseg[p0] + (eseg[NSEG] if wrap else 0),  q = (p0+seg) mod NSEG.
    """
    sb = p["SEG_BITS"]
    nseg = 1 << sb
    E = seg_table(p)
    lcg = (p["SEED"] + 2000) & 0xFFFFFFFF
    ptr = 0
    pre = p["PIPE"]
    # before the first DDS sample reaches the DAC, din = 0 -> ucode = 32768 -> seg = nseg/2
    seq = np.concatenate([np.full(pre, nseg // 2, dtype=np.int64), np.asarray(seg, dtype=np.int64)])
    out = np.empty(len(seq), dtype=np.int64)
    for i in range(len(seq)):
        s = int(seq[i])
        if p["SHUF"] == 1:
            p0 = lcg >> (32 - sb)
        elif p["SHUF"] == 2:
            p0 = ptr
        else:
            p0 = 0
        ps = p0 + s
        q, wrap = ps & (nseg - 1), ps >> sb
        out[i] = int(E[q]) - int(E[p0]) + (int(E[nseg]) if wrap else 0)
        lcg = (lcg * 1664525 + 1013904223) & 0xFFFFFFFF
        if p["SHUF"] == 2:
            ptr = q
    return out[pre:]
 
 
def dyn(p, y):
    """dac_dyn, bit-exact: e = (A|dx| + B dx xn + C dx xn^2 + D|dx|^2 + E dx|dx| + P2 xn^2 + P3 xn^3) >> 16.

    prev is the previous sample of the (periodic, coherent) record, so np.roll is what the
    hardware register holds in steady state.  The output is combinational in the Verilog,
    so this adds no pipeline delay.
    """
    A, B, C, Dq, Eq = (p["DYN_A_Q"], p["DYN_B_Q"], p["DYN_C_Q"], p["DYN_D_Q"], p["DYN_E_Q"])
    P2, P3 = p["DYN_P2_Q"], p["DYN_P3_Q"]
    if not (A or B or C or Dq or Eq or P2 or P3):
        return y
    OW = p["DW"] + p["FRAC"]
    H, SH = OW - 1, 16
    X = np.asarray(y, dtype=np.int64)                     # products stay below 2^40
    D = X - np.roll(X, 1)
    AD = np.abs(D)
    DX = (D * X) >> H
    DX2 = (DX * X) >> H
    AA = (AD * AD) >> H
    DA = (D * AD) >> H
    XX = (X * X) >> H
    E = (A * AD + B * DX + C * DX2 + Dq * AA + Eq * DA
         + P2 * XX + P3 * ((XX * X) >> H) + (1 << (SH - 1))) >> SH
    return np.clip(X + E, -(1 << H), (1 << H) - 1)


def dac(p, code):
    DW, FRAC = p["DW"], p["FRAC"]
    X = np.asarray(code, dtype=np.int64)
    if not p["NONLIN"]:
        return dyn(p, X << FRAC)
    H, OW = DW - 1, DW + FRAC
    ONE, HALF = 1 << H, 1 << (H - 1)
    K3 = (p["INL3_Q"] * 25981 + 5000) // 10000
    X2 = (X * X) >> H
    X3 = (X2 * X) >> H
    E2 = (p["INL2_Q"] * (ONE - X2) + HALF) >> H
    E3 = (K3 * (X3 - X) + HALF) >> H
    seg = (X + (1 << H)) >> (DW - p["SEG_BITS"])
    ES = seg_table(p)[seg] if p["SHUF"] == 0 else shuffle_es(p, seg)
    Y = (X << FRAC) + E2 + E3 + ES
    return dyn(p, np.clip(Y, -(1 << (OW - 1)), (1 << (OW - 1)) - 1))
 
 
def generate(p, m1, n):
    return dac(p, dds_codes(p, m1, n))
 
 
# ---------------- INL / DNL ----------------
def inl_dnl(p):
    # static curve only: shuffle and the slew-dependent term have no static transfer curve
    p = dict(p, SHUF=0, DYN_A_Q=0, DYN_B_Q=0, DYN_C_Q=0, DYN_D_Q=0, DYN_E_Q=0,
                 DYN_P2_Q=0, DYN_P3_Q=0)
    DW, FRAC = p["DW"], p["FRAC"]
    c = np.arange(-(1 << (DW - 1)), 1 << (DW - 1), dtype=np.int64)
    y = dac(p, c).astype(np.float64) / (1 << FRAC)            # in LSB
    dnl = np.diff(y) - 1.0
    inl_ep = y - np.linspace(y[0], y[-1], len(y))             # endpoint
    k = np.polyfit(c, y, 1)
    inl_bf = y - np.polyval(k, c)                             # best fit
    return c, y, inl_ep, inl_bf, dnl
 
 
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--params", default="", help='e.g. "NONLIN=1 INL2_Q=64 INL3_Q=0 DNL_Q=0 SHUF=2"')
    ap.add_argument("--inl-dnl", action="store_true")
    ap.add_argument("--plot", help="save INL/DNL plot to this png")
    ap.add_argument("--m", type=int)
    ap.add_argument("--m2", type=int, help="two-tone test (sets TONES=2, M_SPACING=m2-m)")
    ap.add_argument("--fdac", type=float, default=sfdr.FDAC_MHZ)
    ap.add_argument("--csv")
    ap.add_argument("--tag", default="ref")
    ap.add_argument("--write", help="write the expected record (int32, SKIP zeros + NFFT samples)")
    a = ap.parse_args()
    p = parse_params(a.params)
    sfdr.FDAC_MHZ = a.fdac
 
    if a.inl_dnl:
        c, y, ep, bf, dnl = inl_dnl(p)
        print(f"INL endpoint: {ep.min():+.2f} .. {ep.max():+.2f} LSB | best fit: {bf.min():+.2f} .. {bf.max():+.2f} LSB")
        print(f"DNL: {dnl.min():+.2f} .. {dnl.max():+.2f} LSB")
        if a.plot:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
            ax[0].plot(c, ep, lw=0.8, label="endpoint")
            ax[0].plot(c, bf, lw=0.8, label="best fit")
            ax[0].set_ylabel("INL, LSB"); ax[0].legend(); ax[0].grid(alpha=.3)
            ax[1].plot(c[:-1], dnl, lw=0.6)
            ax[1].set_ylabel("DNL, LSB"); ax[1].set_xlabel("code"); ax[1].grid(alpha=.3)
            ax[0].set_title(a.params or "ideal")
            fig.tight_layout(); fig.savefig(a.plot, dpi=130)
 
    if a.m is not None:
        if a.m2 is not None:
            p["TONES"], p["M_SPACING"] = 2, a.m2 - a.m
        n = 1 << p["LOG2N"]
        if p["SHUF"]:
            # shuffle state runs from clock 0: simulate the whole record, then cut the same
            # window the measurement sees (raw[SKIP+i] = model[SKIP+i-DELAY])
            lo = sfdr.SKIP - p["DELAY"]
            x = generate(p, a.m, n + sfdr.SKIP)[lo:lo + n].astype(np.float64)
        else:
            x = generate(p, a.m, n).astype(np.float64)
        bits = p["DW"] - 1 + p["FRAC"]
        r = (sfdr.measure_two(x, bits, a.m, a.m2, a.tag, True) if a.m2 is not None
             else sfdr.measure_tone(x, bits, a.m, a.tag, True))
        if a.csv:
            r.update(tag=a.tag, file="model_ref")
            sfdr.append_csv(a.csv, r)
        if a.write:
            np.concatenate([np.zeros(sfdr.SKIP), x]).astype(np.int32).tofile(a.write)
 
 
if __name__ == "__main__":
    main()
 