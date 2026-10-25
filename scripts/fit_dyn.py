#!/usr/bin/env python3
"""
Fit the five dac_dyn coefficients (DYN_A_Q..DYN_E_Q) to AD9081 Table 16.

Stage 1 of the plan: the static curve (Table 3 INL/DNL) plus shuffle is ~17 dB cleaner than
the datasheet, and it does not depend on frequency at all.  What the datasheet shows is a
roll-off, so the missing part is the switching (slew-dependent) error.  dac_dyn adds

    e[n] = ( A*|dx| + B*dx*xn + C*dx*xn^2 + D*|dx|*|dx|n + E*dx*|dx|n ) >> 16 ,
    dx = x[n]-x[n-1],  xn = x / full scale,  |dx|n = |dx| / full scale

The error is *linear* in every coefficient, so the fit does not need to re-run the model:
for each test point we build the five basis error signals once, FFT them, and the spectrum
of any coefficient vector is a weighted sum.  Only the final check re-runs the real model.

    python3 fit_dyn.py                 # fit, print the coefficients and the check table
    python3 fit_dyn.py --json dyn.json # also write them for build.sh
"""
import argparse
import json
import os
import sys

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_ref  # noqa: E402
import sfdr  # noqa: E402

NFFT, SKIP = sfdr.NFFT, sfdr.SKIP
FDAC = 12000.0
BITS = 19
# AD9081 Rev.0, Table 16, fDAC = 12 GSPS, shuffle on
DS_SFDR = {70: 80, 100: 77, 500: 76, 900: 77, 1900: 79, 2600: 75, 3700: 69, 4500: 68}
DS_IMD3 = {1900: -69, 2600: -72, 3700: -72}
BASE = "NONLIN=1 INL2_Q=48 INL3_Q=48 DNL_Q=56 SEED=8 SHUF=1"
NAMES = ["A", "B", "C", "D", "E", "P2", "P3"]
# The five slew terms vanish as fOUT -> 0, so they cannot produce the 80 dBc that Table 16 shows
# at 70 MHz: that corner is frequency-flat.  The INL of Table 3 is far too small for it (8 LSB
# of INL, and the bow is mostly spent on the segment mismatch, give HD2 near -93 dBc with
# shuffle on), so the flat part is modelled as the memoryless distortion of the analog output
# stage, P2*xn^2 + P3*xn^3 - a different block, not limited by Table 3 and not touched by
# shuffling.  It is fitted together with the slew terms (the error is linear in all of them).


def m_of(f):
    x = f * NFFT / FDAC
    return 2 * int(x / 2) + 1


def basis(y):
    """error signals per unit coefficient: five slew terms (scale 2^-16) + the two INL terms"""
    H = BITS
    X = y.astype(np.int64)
    D = X - np.roll(X, 1)
    AD = np.abs(D)
    DX = (D * X) >> H
    XX = (X * X) >> H
    return np.stack([AD, DX, (DX * X) >> H, (AD * AD) >> H, (D * AD) >> H,
                     XX, (XX * X) >> H]).astype(np.float64) / 2.0 ** 16


def point(m, m2=None):
    """baseline record (shuffle on, no dynamics) + the basis signals, reduced to the spur bins.

    The cost is evaluated thousands of times, so the full 16k-bin spectrum is collapsed once:
    only the harmonics 2..10 (and, for two tones, the IMD products) can become the worst spur,
    everything else is the shuffle noise floor, whose peak is kept as a constant ceiling.
    """
    p = model_ref.parse_params(BASE + (" TONES=2 M_SPACING=%d" % (m2 - m) if m2 else ""))
    lo = SKIP - p["DELAY"]
    y = model_ref.generate(p, m, NFFT + SKIP)[lo:lo + NFFT].astype(np.int64)
    F0 = np.fft.rfft(y.astype(np.float64))
    FB = np.fft.rfft(basis(y), axis=1)

    f = lambda b: sfdr.fold(b, NFFT)                                    # noqa: E731
    bins = [f(k * m) for k in range(2, 11)]
    if m2:
        bins += [f(2 * m - m2), f(2 * m2 - m), f(m + m2), f(2 * m2), f(3 * m2),
                 f(3 * m - 2 * m2), f(3 * m2 - 2 * m), f(2 * m + m2), f(2 * m2 + m)]
    bins = sorted(set(b for b in bins if b not in (0, m, m2)))
    imd = [bins.index(f(2 * m - m2)), bins.index(f(2 * m2 - m))] if m2 else []

    keep = np.ones(len(F0), bool)
    keep[0] = keep[m] = False
    if m2:
        keep[m2] = False
    keep[bins] = False
    floor = np.abs(F0[keep]).max()                 # shuffle noise peak (independent of the fit)
    car = max(abs(F0[m]), abs(F0[m2])) if m2 else abs(F0[m])
    return dict(m=m, m2=m2, car=car, floor=floor, f0=F0[bins], fb=FB[:, bins], imd=imd)


def amps(pt, c):
    return np.abs(pt["f0"] + c @ pt["fb"])


def sfdr_of(pt, c):
    return -20 * np.log10(max(amps(pt, c).max(), pt["floor"]) / pt["car"])


def imd3_of(pt, c):
    return 20 * np.log10(amps(pt, c)[pt["imd"]].max() / pt["car"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()

    print("building the basis ...")
    one = {f: point(m_of(f)) for f in DS_SFDR}
    two = {f: point(m_of(f), m_of(f) + 2) for f in DS_IMD3}

    def cost(c):
        e = [sfdr_of(one[f], c) - t for f, t in DS_SFDR.items()]
        e += [imd3_of(two[f], c) - t for f, t in DS_IMD3.items()]
        return float(np.mean(np.square(e)))

    best = None
    rng = np.random.default_rng(0)
    for k in range(200):                       # multistart: the cost has plateaus (max over spurs)
        x0 = np.zeros(7) if k == 0 else np.r_[rng.uniform(-400, 400, 5), rng.uniform(-60, 60, 2)]
        r = minimize(cost, x0, method="Nelder-Mead",
                     options=dict(maxiter=8000, maxfev=8000, xatol=1e-3, fatol=1e-6))
        if best is None or r.fun < best.fun:
            best = r
    c = np.round(best.x)                      # the Verilog parameters are integers
    print(f"\nrms error {np.sqrt(cost(c)):.2f} dB")
    print("DYN " + "  ".join(f"{n}_Q={int(v)}" for n, v in zip(NAMES, c)))
    print(f"output stage: HD2 floor {20 * np.log10(abs(c[5]) / 2 ** 16 * 0.446 + 1e-30):.1f} dBc, "
          f"HD3 floor {20 * np.log10(abs(c[6]) / 2 ** 16 * 0.446 ** 2 * 0.75 + 1e-30):.1f} dBc "
          f"(at -7 dBFS, frequency-flat)")

    print("\n| fOUT, MHz | SFDR fit | Table 16 | d | IMD3 fit | Table 16 | d |")
    for f in DS_SFDR:
        s = sfdr_of(one[f], c)
        i = f"{imd3_of(two[f], c):.1f} | {DS_IMD3[f]} | {imd3_of(two[f], c) - DS_IMD3[f]:+.1f}" \
            if f in two else " |  | "
        print(f"| {f} | {s:.1f} | {DS_SFDR[f]} | {s - DS_SFDR[f]:+.1f} | {i} |")

    params = " ".join(f"DYN_{n}_Q={int(v)}" for n, v in zip(NAMES, c))
    print("\nbuild.sh / model_ref.py parameters:\n  " + params)
    if a.json:
        json.dump(dict(zip([f"DYN_{n}_Q" for n in NAMES], [int(v) for v in c]),
                       rms_db=float(np.sqrt(cost(c))), params=params), open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
