#!/usr/bin/env python3
"""
Summary of a build.sh run: tables + plots, compared with AD9081 Table 16 (fDAC = 12 GSPS).

  python3 report.py results/            -> results/summary.md, results/sfdr_vs_fout.png, results/imd3_vs_fout.png

Inputs (written by build.sh):
  results.csv    - measured on the GNU Radio File Sink output
  reference.csv  - the same points from model_ref.py (bit-exact Python model of dds_gr_all.v)
The difference measured - reference must be ~0 dB: it checks the whole
Verilog -> Verilator -> GNU Radio -> file chain.
"""
import os
import sys

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# AD9081 Rev.0, Table 16, fDAC = 12 GSPS
DS_SFDR = {70: 80, 100: 77, 500: 76, 900: 77, 1900: 79, 2600: 75, 3700: 69, 4500: 68}   # dBc, -7 dBFS, shuffle on
DS_IMD3 = {1900: -69, 2600: -72, 3700: -72}                                           # dBc, -6 dBFS/tone, 1 MHz spacing

# categorical slots in fixed order (validated reference palette, light mode)
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "h"]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

DESCR = {
    "ideal": "ideal DAC (DDS quantization only)",
    "aw14":  "ideal DAC, AW=14 (phase truncation)",
    "inl2":  "INL bow 8 LSB (even -> HD2)",
    "inl3":  "INL S-curve 8 LSB (odd -> HD3)",
    "dnl":   "segment mismatch, DNL 3.5 LSB",
    "full":  "INL 7.9 LSB + DNL 3.5 LSB (Table 3)",
}


def db(v):
    """table cell: very low levels are below the model's numeric floor"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    return "< -150" if v < -150 else f"{v:.1f}"


def style(ax, title, ylabel):
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.set_xlabel("fOUT, MHz (fDAC = 12 GSPS)", color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(True, color=GRID, lw=0.8)
    ax.tick_params(colors=MUTED)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)


def plot(df, col, ds, ylabel, title, path, tones):
    d = df[df.tones == tones]
    if d.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (tag, g) in enumerate(d.groupby("tag", sort=False)):
        g = g.sort_values("fout_mhz")
        ax.plot(g.fout_mhz, g[col], color=SLOTS[i % 8], marker=MARKERS[i % 8], ms=7, lw=2,
                label=f"{tag}: {DESCR.get(tag, '')}")
    ax.plot(list(ds), list(ds.values()), color=INK, marker="*", ms=12, lw=1.2, ls="--",
            label="AD9081 datasheet, Table 16")
    style(ax, title, ylabel)
    ax.legend(fontsize=8, frameon=False, loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main():
    res = sys.argv[1] if len(sys.argv) > 1 else "results"
    meas = pd.read_csv(os.path.join(res, "results.csv"))
    ref_p = os.path.join(res, "reference.csv")
    ref = pd.read_csv(ref_p) if os.path.exists(ref_p) else None
    meas = meas.drop_duplicates(["tag", "tones", "m1", "m2"], keep="last")
    order = list(dict.fromkeys(meas.tag))

    plot(meas, "sfdr_dbc", DS_SFDR, "SFDR, dBc", "Single tone, -7 dBFS: SFDR",
         os.path.join(res, "sfdr_vs_fout.png"), 1)
    plot(meas, "imd3_dbc", DS_IMD3, "IMD3, dBc", "Two tones, -6 dBFS per tone: IMD3",
         os.path.join(res, "imd3_vs_fout.png"), 2)

    out = ["# DAC nonlinearity: measured (GNU Radio chain) vs AD9081 Table 16", ""]
    if ref is not None:
        ref = ref.drop_duplicates(["tag", "tones", "m1", "m2"], keep="last")
        k = ["tag", "tones", "m1", "m2"]
        j = meas.merge(ref, on=k, suffixes=("", "_ref"))
        cols = ["sfdr_dbc", "hd2_dbc", "hd3_dbc", "imd3_dbc"]
        dev = max((np.nanmax(np.abs(pd.to_numeric(j[c], errors="coerce") -
                                    pd.to_numeric(j[c + "_ref"], errors="coerce")))
                   for c in cols if j[c].notna().any()), default=np.nan)
        out += [f"Chain check: max |measured - model_ref| = {dev:.3f} dB over {len(j)} points "
                f"({'OK' if dev < 0.05 else 'MISMATCH - check wrapper/File Sink/SKIP'})", ""]

    s = meas[meas.tones == 1]
    if not s.empty:
        out += ["## Single tone, -7 dBFS", "",
                "| scenario | fOUT, MHz | SFDR, dBc | worst spur | HD2, dBc | HD3, dBc | Table 16 SFDR |",
                "|---|---|---|---|---|---|---|"]
        for tag in order:
            for _, r in s[s.tag == tag].sort_values("fout_mhz").iterrows():
                dsv = DS_SFDR.get(int(round(r.fout_mhz / 10.0) * 10), "")
                out.append(f"| {tag} | {r.fout_mhz:.0f} | {r.sfdr_dbc:.1f} | {r.spur_label if isinstance(r.spur_label, str) else ''} "
                           f"| {db(r.hd2_dbc)} | {db(r.hd3_dbc)} | {dsv} |")
        out.append("")
    t = meas[meas.tones == 2]
    if not t.empty:
        out += ["## Two tones, -6 dBFS per tone", "",
                "| scenario | fc, MHz | IMD3 2f1-f2 | IMD3 2f2-f1 | IMD3 worst, dBc | Table 16 IMD3 |",
                "|---|---|---|---|---|---|"]
        for tag in order:
            for _, r in t[t.tag == tag].sort_values("fout_mhz").iterrows():
                dsv = DS_IMD3.get(int(round(r.fout_mhz / 100.0) * 100), "")
                out.append(f"| {tag} | {r.fout_mhz:.0f} | {db(r.imd3_lo_dbc)} | {db(r.imd3_hi_dbc)} | {db(r.imd3_dbc)} | {dsv} |")
        out.append("")
    out += ["![SFDR](sfdr_vs_fout.png)", "", "![IMD3](imd3_vs_fout.png)", ""]
    with open(os.path.join(res, "summary.md"), "w") as f:
        f.write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
