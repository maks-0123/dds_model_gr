#!/usr/bin/env python3
"""
Итоги прогона build.sh: таблицы и графики рядом с Table 16 AD9081 (fDAC = 12 ГГц).

  python3 report.py results/  -> results/summary.md and plots:
      sfdr_vs_fout.png, imd3_vs_fout.png             (nonlinearity / shuffle scenarios)
      snr_jitter.png, nsd_jitter.png                 (jitter scenarios)
      shuffle_bands.png                              (noise density by sub-band: shuffle off / rotation / DWA)
      seeds.png                                      (seed study, if seeds.csv exists)

Inputs (written by build.sh):
  results.csv    - measured on the GNU Radio File Sink output
  reference.csv  - the same points from model_ref.py (bit-exact Python model of dds_gr_all.v)
  seeds.csv, seeds_ref.csv - optional, SEEDSTUDY=1
  raw/*.bin      - records (used for the sub-band noise of the shuffle scenarios)
The difference measured - reference must be ~0 dB: it checks the whole
Verilog -> Verilator -> GNU Radio -> file chain.
"""
import os
import re
import sys

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# AD9081 Rev.0, Table 16, fDAC = 12 GSPS
DS_SFDR = {70: 80, 100: 77, 500: 76, 900: 77, 1900: 79, 2600: 75, 3700: 69, 4500: 68}   # dBc, -7 dBFS, shuffle on
DS_IMD3 = {1900: -69, 2600: -72, 3700: -72}                                           # dBc, -6 dBFS/tone, 1 MHz spacing
# Table 16, single-tone NSD, fDAC = 12 GSPS, 0 dBFS, 10 % away from fOUT, shuffle off
DS_NSD = {150: -168, 500: -167, 950: -165, 1840: -162, 2650: -160, 3700: -155, 4500: -154}  # dBc/Hz
FDAC_HZ = 12e9
SKIP = 1000              # keep consistent with build.sh / sfdr.py
NFFT = 32768
NBANDS = 6               # sub-bands of 0..fDAC/2 for the shuffle noise shaping (1 GHz each)
# The plots go into REPORT.pdf as images, so they are drawn at the width they are placed at
# (A4 minus margins) and at print resolution: scaling a figure down blurs it and shrinks its text.
FIGW = 7.1               # inches: page width between the margins of make_report.py
DPI = 300

# categorical slots in fixed order (validated reference palette, light mode)
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "h"]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

DESCR = {
    "ideal": "идеальный ЦАП (только квантование DDS)",
    "aw14":  "идеальный ЦАП, AW=14 (усечение фазы)",
    "inl2":  "INL «дуга» 8 МЗР (чётная → HD2)",
    "inl3":  "INL «S-кривая» 8 МЗР (нечётная → HD3)",
    "dnl":   "рассогласование сегментов, DNL 3.5 МЗР",
    "full":  "INL 7.9 МЗР + DNL 3.5 МЗР (Table 3), без перемешивания",
    "shuf_rot": "ЦАП Table 3, перемешивание вращением",
    "shuf_dwa": "ЦАП Table 3, перемешивание DWA",
    "jit25":  "идеальный ЦАП + джиттер 25 фс",
    "jit50":  "идеальный ЦАП + джиттер 50 фс",
    "jit100": "идеальный ЦАП + джиттер 100 фс",
    "jit200": "идеальный ЦАП + джиттер 200 фс",
    "full_jit50": "нелинейность Table 3 + джиттер 50 фс",
    "full_jit58": "Table 3, без перемешивания + джиттер 58 фс",
    "shuf_rot_jit58": "Table 3, вращение + джиттер 58 фс",
    "shuf_dwa_jit58": "Table 3, DWA + джиттер 58 фс",
    "dyn": "статика + динамическая нелинейность, без перемешивания",
    "shuf_rot_dyn": "статика + вращение + динамическая нелинейность",
    "ad9081": "полная модель: статика + вращение + динамика + джиттер 58 фс + тепловой пол",
}
STAGE1 = ["shuf_rot", "shuf_rot_dyn", "ad9081"]   # shuffle only -> + dynamics -> + jitter/noise
TOL = 3.0                                          # stage 1 acceptance: +-3 dB to Table 16
SHUF_MODES = ["full", "shuf_rot", "shuf_dwa"]
SEED_MODES = SHUF_MODES + ["shuf_rot_dyn"]          # shuffle off / random rotation / DWA


def is_jit(tag):
    return "jit" in str(tag)


def is_pure_jit(tag):
    """ideal DAC + jitter: the only case where the SNR theory line applies"""
    return re.fullmatch(r"jit\d+", str(tag)) is not None


def sigma_of(tag):
    """jitter in fs from the scenario name: jit50 -> 50, full_jit50 -> 50, ideal -> 0"""
    t = str(tag)
    return float(t[t.rfind("jit") + 3:]) if "jit" in t else 0.0


def nrz(f):
    """the DAC holds each sample: the error is the step x[n]-x[n-1], not x'(t)*Ts -> sin(pi f/fs)/(pi f/fs)"""
    u = np.pi * np.asarray(f, float) / FDAC_HZ
    return np.sin(u) / u


def snr_theory(f, sigma_fs, q_db):
    """jitter SNR (with NRZ factor) combined with the quantization floor q_db"""
    pj = (2 * np.pi * np.asarray(f, float) * sigma_fs * 1e-15 * nrz(f)) ** 2
    return -10 * np.log10(10 ** (-q_db / 10) + pj)


def fit_sigma(ds):
    """sigma (fs) and floor (dBc/Hz) that best fit the datasheet NSD: floor + white jitter over 0..fs/2"""
    f = np.array(list(ds), float) * 1e6
    y = np.array(list(ds.values()), float)
    best = (1e9, 0, 0)
    for n0 in np.arange(-180, -160, 0.1):
        for sg in np.arange(5, 400, 0.5):
            pj = (2 * np.pi * f * sg * 1e-15 * nrz(f)) ** 2 / (FDAC_HZ / 2)
            e = np.sqrt(np.mean((10 * np.log10(10 ** (n0 / 10) + pj) - y) ** 2))
            if e < best[0]:
                best = (e, sg, n0)
    return best[1], best[2], best[0]


def db(v):
    """table cell: very low levels are below the model's numeric floor"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    if np.isnan(v):
        return ""
    return "< -150" if v < -150 else f"{v:.1f}"


def num(v, fmt="{:.1f}"):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    return "" if np.isnan(v) else fmt.format(v)


def style(ax, title, ylabel, xlabel="fOUT, МГц (fDAC = 12 ГГц)"):
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(True, color=GRID, lw=0.8)
    ax.tick_params(colors=MUTED)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)


def snr_col(df):
    return "snr_dB" if "snr_dB" in df else ("snr_db" if "snr_db" in df else None)


# ---------------------------------------------------------------- jitter
def jitter_section(meas, res):
    """SNR / NSD of the jitter scenarios vs theory and vs Table 16. Returns markdown lines."""
    col = snr_col(meas)
    if col is None:
        return []
    d = meas[(meas.tones == 1) & (meas.tag.map(is_jit) | (meas.tag == "ideal"))].copy()
    d = d[pd.to_numeric(d[col], errors="coerce").notna()]
    if d.empty or not d.tag.map(is_jit).any():
        return []
    d[col] = d[col].astype(float)
    ideal = d[d.tag == "ideal"][col]
    q = float(ideal.mean()) if len(ideal) else 91.13
    sg_fit, n0_fit, e_fit = fit_sigma(DS_NSD)

    tags = list(dict.fromkeys(d.tag))
    ff = np.geomspace(50e6, 5e9, 200)

    # --- SNR vs fOUT, model points + theory lines (theory only for ideal DAC + jitter) ---
    fig, ax = plt.subplots(figsize=(FIGW, 4.7))
    for i, tag in enumerate(tags):
        g = d[d.tag == tag].sort_values("fout_mhz")
        c = SLOTS[i % 8]
        ax.plot(g.fout_mhz, g[col], color=c, marker=MARKERS[i % 8], ms=8, lw=0, zorder=5,
                label=f"{tag}: {DESCR.get(tag, '')}")
        if is_pure_jit(tag) or tag == "ideal":
            ax.plot(ff / 1e6, snr_theory(ff, sigma_of(tag), q), color=c, lw=1.4, ls="--", zorder=3)
    ax.set_xscale("log")
    style(ax, "Джиттер такта: SNR от fOUT\n(точки - модель, пунктир - \u221220lg(2\u03c0f\u03c3) с шумом квантования)",
          "SNR, дБ")
    ax.legend(fontsize=7.5, frameon=False, loc="upper left", bbox_to_anchor=(0, -0.21), ncol=1)
    fig.tight_layout(); fig.savefig(os.path.join(res, "snr_jitter.png"), dpi=DPI,
                                        bbox_inches="tight", pad_inches=0.02); plt.close(fig)

    # --- NSD vs fOUT, model vs Table 16 ---
    fig, ax = plt.subplots(figsize=(FIGW, 4.7))
    for i, tag in enumerate(tags):
        g = d[d.tag == tag].sort_values("fout_mhz")
        ax.plot(g.fout_mhz, -g[col] - 10 * np.log10(FDAC_HZ / 2), color=SLOTS[i % 8], marker=MARKERS[i % 8],
                ms=7, lw=1.2, label=f"модель {tag}")
    pj = (2 * np.pi * ff * sg_fit * 1e-15 * nrz(ff)) ** 2 / (FDAC_HZ / 2)
    ax.plot(ff / 1e6, 10 * np.log10(10 ** (n0_fit / 10) + pj), color=INK, lw=1.2, ls=":",
            label=f"подгонка под Table 16: \u03c3 = {sg_fit:.0f} фс, пол {n0_fit:.1f} dBc/Hz")
    ax.plot(list(DS_NSD), list(DS_NSD.values()), color=INK, marker="*", ms=13, lw=0, zorder=10,
            label="NSD AD9081, Table 16 (0 dBFS, без перемешивания)")
    ax.set_xscale("log")
    style(ax, "Спектральная плотность шума от fOUT: модель и даташит AD9081", "NSD, dBc/Hz")
    ax.legend(fontsize=7.5, frameon=False, loc="upper left", bbox_to_anchor=(0, -0.21), ncol=1)
    fig.tight_layout(); fig.savefig(os.path.join(res, "nsd_jitter.png"), dpi=DPI,
                                        bbox_inches="tight", pad_inches=0.02); plt.close(fig)

    out = ["## Джиттер такта, однотон \u22127 dBFS", "",
           f"Пол квантования (сценарий ideal): SNR = {q:.2f} дБ. "
           f"Теория - джиттер \u221220lg(2\u03c0f\u03c3\u00b7sinc) вместе с этим полом "
           f"(только для идеального ЦАП с джиттером: при нелинейности или перемешивании "
           f"добавочный шум - не джиттер).", "",
           "| сценарий | \u03c3, фс | fOUT, МГц | SNR, дБ | теория, дБ | \u0394, дБ | NSD, dBc/Hz | \u03c3 из SNR, фс | SFDR, dBc |",
           "|---|---|---|---|---|---|---|---|---|"]
    for tag in tags:
        for _, r in d[d.tag == tag].sort_values("fout_mhz").iterrows():
            f = r.fout_mhz * 1e6
            sg = sigma_of(tag)
            th = float(snr_theory(f, sg, q))
            pj = 10 ** (-r[col] / 10) - 10 ** (-q / 10)          # jitter part of the noise
            est = (np.sqrt(pj) / (2 * np.pi * f * float(nrz(f))) * 1e15) \
                if (is_pure_jit(tag) and pj > 0.25 * 10 ** (-q / 10)) else np.nan
            th_s = f"{th:.2f}" if is_pure_jit(tag) or tag == "ideal" else ""
            dl_s = f"{r[col] - th:+.2f}" if th_s else ""
            out.append(f"| {tag} | {sg:.0f} | {r.fout_mhz:.0f} | {r[col]:.2f} | "
                       f"{th_s} | {dl_s} | {-r[col] - 10 * np.log10(FDAC_HZ / 2):.1f} | "
                       f"{'' if np.isnan(est) else f'{est:.1f}'} | {r.sfdr_dbc:.1f} |")
    out += ["", f"Подгонка NSD из Table 16 (0 dBFS): \u03c3 \u2248 **{sg_fit:.0f} фс**, пол {n0_fit:.1f} dBc/Hz "
            f"(ср.-кв. ошибка {e_fit:.2f} дБ). Модель работает на \u22127 dBFS, поэтому её пол квантования "
            f"в dBc/Hz на 7 дБ выше, чем при 0 dBFS; джиттерная часть (dBc/Hz) от уровня не зависит.", "",
            "![SNR](snr_jitter.png)", "", "![NSD](nsd_jitter.png)", ""]
    return out



# ---------------------------------------------------------------- stage 1: dynamic nonlinearity
def stage1_section(meas, res):
    """Модель с динамическим членом рядом с Table 16 (критерий ±3 дБ по SFDR, IMD3, NSD)."""
    tags = [t for t in STAGE1 if t in set(meas.tag)]
    if "shuf_rot_dyn" not in tags and "ad9081" not in tags:
        return []
    col = snr_col(meas)
    final = "ad9081" if "ad9081" in tags else "shuf_rot_dyn"
    one = meas[(meas.tones == 1) & meas.tag.isin(tags)]
    two = meas[(meas.tones == 2) & meas.tag.isin(tags)]

    out = ["## Этап 1: динамическая (зависящая от скорости) нелинейность", "",
           "Статическая кривая не зависит от частоты, поэтому с включённым перемешиванием она "
           "примерно на 17 дБ чище Table 16 и совершенно плоская. Модуль `dac_dyn` добавляет ошибку "
           "переключения e = (A|dx| + B·dx·x + C·dx·x² + D|dx|² + E·dx|dx| + P2·x² + P3·x³)/2¹⁶, "
           "где dx = x[n]−x[n−1]. Члены со скоростью растут с частотой (dx ≈ 2·sin(πf/fDAC)): чётные "
           "дают HD2, нечётные - HD3 и IMD3; P2 и P3 - безынерционное искажение выходного каскада, "
           "плоское по частоте. Коэффициенты подобраны под Table 16 скриптом `fit_dyn.py`.", ""]

    j = os.path.join(res, "dyn_fit.json")
    if os.path.exists(j):
        import json
        d = json.load(open(j))
        out += [f"Подобранные коэффициенты: `{d['params']}` "
                f"(ср.-кв. ошибка подгонки {d['rms_db']:.2f} дБ).", ""]

    out += [f"| fOUT, МГц | SFDR {final} | Table 16 | Δ | IMD3 {final} | Table 16 | Δ | "
            f"NSD, dBc/Hz | NSD Table 16 |", "|---|---|---|---|---|---|---|---|---|"]
    ok = True
    for f in sorted(one[one.tag == final].fout_mhz.round(0).unique()):
        r = one[(one.tag == final) & (one.fout_mhz.round(0) == f)].iloc[0]
        ds = DS_SFDR.get(int(round(f / 10.0) * 10))
        t = two[(two.tag == final) & (two.fout_mhz.round(0).between(f - 2, f + 2))]
        di = DS_IMD3.get(int(round(f / 100.0) * 100))
        im = float(t.imd3_dbc.iloc[0]) if len(t) else np.nan
        # NSD: the datasheet grid is not the SFDR grid, take the nearest point
        kn = min(DS_NSD, key=lambda k: abs(k - f))
        dn = DS_NSD[kn] if abs(kn - f) < 0.2 * f else None
        nsd = float(r.get("nsd_dbc_hz", np.nan))
        dsf = (r.sfdr_dbc - ds) if ds else np.nan
        dim = (im - di) if (di and not np.isnan(im)) else np.nan
        for v in (dsf, dim):
            if not np.isnan(v) and abs(v) > TOL:
                ok = False
        out.append(f"| {f:.0f} | {r.sfdr_dbc:.1f} | {ds or ''} | {num(dsf, '{:+.1f}')} | "
                   f"{num(im)} | {di or ''} | {num(dim, '{:+.1f}')} | {num(nsd)} | "
                   f"{dn if dn is not None else ''} |")
    out += ["", "NSD измерена на −7 dBFS, в даташите - при 0 dBFS: тепловая часть модели и шум "
            "квантования поэтому на 7 дБ выше в dBc/Hz, чем значение даташита, а джиттерная часть от "
            "уровня не зависит и сравнивается напрямую. Отсюда и картина: точки на высоких fOUT, где "
            "правит джиттер, совпадают, а низкочастотные лежат примерно на 7 дБ выше.", "",
            f"Критерий (±{TOL:.0f} дБ к Table 16 по SFDR и IMD3): "
            f"**{'выполнен' if ok else 'выполнен не во всех точках'}**.", ""]

    # --- SFDR / IMD3 of the three stages vs the datasheet ---
    fig, axs = plt.subplots(2, 1, figsize=(FIGW, 8.4))
    for ax, (d, c, ds, ttl, yl) in zip(axs, [
            (one, "sfdr_dbc", DS_SFDR, "Однотон −7 dBFS: SFDR", "SFDR, dBc"),
            (two, "imd3_dbc", DS_IMD3, "Двухтон −6 dBFS на тон: IMD3", "IMD3, dBc")]):
        for i, t in enumerate(tags):
            g = d[d.tag == t].sort_values("fout_mhz")
            if len(g):
                ax.plot(g.fout_mhz, pd.to_numeric(g[c], errors="coerce"), color=SLOTS[i],
                        marker=MARKERS[i], ms=8, lw=2, label=t)
        fx, fy = np.array(list(ds), float), np.array(list(ds.values()), float)
        ax.fill_between(fx, fy - TOL, fy + TOL, color=GRID, zorder=0, label=f"Table 16 ±{TOL:.0f} дБ")
        ax.plot(fx, fy, color=INK, marker="*", ms=12, lw=1.2, ls="--", label="AD9081, Table 16")
        ax.set_xscale("log")
        style(ax, ttl, yl)
        ax.legend(fontsize=8, frameon=False)
    fig.tight_layout(); fig.savefig(os.path.join(res, "stage1_dyn.png"), dpi=DPI,
                                        bbox_inches="tight", pad_inches=0.02); plt.close(fig)
    out += ["![этап 1](stage1_dyn.png)", ""]
    if col:
        out += ["SNR в полной полосе (те же точки): " + ", ".join(
            f"{t} {pd.to_numeric(one[one.tag == t][col], errors='coerce').median():.1f} дБ"
            for t in tags if len(one[one.tag == t])), ""]
    return out


# ---------------------------------------------------------------- shuffle
def fold(b, n=NFFT):
    b = b % n
    return n - b if b > n // 2 else b


def band_nsd(path, m, nb=NBANDS):
    """Noise density (dBc/Hz) in nb equal sub-bands of 0..fDAC/2, from the raw record.
    Excluded: DC, the carrier and harmonics 2..10 (folded) - same as the SNR in sfdr.py."""
    if not os.path.exists(path):
        return None
    x = np.fromfile(path, dtype=np.int32)
    if len(x) < SKIP + NFFT:
        return None
    x = x[SKIP:SKIP + NFFT].astype(np.float64)
    P = np.abs(np.fft.rfft(x)) ** 2
    pc = P[m]
    keep = np.ones(len(P), bool)
    keep[0] = False
    for k in range(1, 11):
        keep[fold(k * m)] = False
    bins = np.arange(len(P))
    edges = np.linspace(0, NFFT // 2 + 1, nb + 1)
    binw = FDAC_HZ / NFFT
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = keep & (bins >= lo) & (bins < hi)
        out.append(10 * np.log10(P[sel].mean() / pc) - 10 * np.log10(binw))
    return out


def shuffle_section(meas, res):
    """Без перемешивания / вращение / DWA: SFDR, SNR и шум по поддиапазонам."""
    col = snr_col(meas)
    s = meas[(meas.tones == 1) & meas.tag.isin(SHUF_MODES)]
    if s.empty or not s.tag.isin(["shuf_rot", "shuf_dwa"]).any():
        return []
    out = ["## Перемешивание: выключено / вращение / DWA (однотон, −7 dBFS)", "",
           "INL и DNL в Table 3 заданы при выключенном перемешивании, а SFDR и IMD3 в Table 16 - при "
           "включённом. Вращение превращает спуры сегментов в белый шум; у DWA та же полная мощность "
           "ошибки, но она сдвинута к fDAC/2, поэтому SNR в полной полосе одинаков и разница видна "
           "только по поддиапазонам.", "",
           "| fOUT, МГц | SFDR выкл | SFDR вращ | SFDR DWA | SNR выкл, дБ | SNR вращ, дБ | SNR DWA, дБ | ΔSNR вращ | SFDR Table 16 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for f in sorted(s.fout_mhz.round(0).unique()):
        row = {t: s[(s.tag == t) & (s.fout_mhz.round(0) == f)] for t in SHUF_MODES}
        g = lambda t, c: (float(row[t][c].iloc[0]) if (len(row[t]) and c) else np.nan)  # noqa: E731
        dsnr = g("shuf_rot", col) - g("full", col)
        dsv = DS_SFDR.get(int(round(f / 10.0) * 10), "")
        out.append(f"| {f:.0f} | {num(g('full', 'sfdr_dbc'))} | {num(g('shuf_rot', 'sfdr_dbc'))} | "
                   f"{num(g('shuf_dwa', 'sfdr_dbc'))} | {num(g('full', col))} | {num(g('shuf_rot', col))} | "
                   f"{num(g('shuf_dwa', col))} | {num(dsnr, '{:+.1f}')} | {dsv} |")
    out.append("")

    # --- noise by sub-band at the frequency closest to 900 MHz ---
    f0 = s.fout_mhz.iloc[(s.fout_mhz - 900).abs().argsort().iloc[0]]
    bands = {}
    for t in SHUF_MODES:
        r = s[(s.tag == t) & (s.fout_mhz == f0)]
        if len(r) and "file" in r:
            v = band_nsd(os.path.join(res, "raw", str(r.file.iloc[0])), int(r.m1.iloc[0]))
            if v is not None:
                bands[t] = v
    if bands:
        step = FDAC_HZ / 2 / NBANDS / 1e6
        centers = [(i + 0.5) * step for i in range(NBANDS)]
        fig, ax = plt.subplots(figsize=(FIGW, 4.4))
        for i, (t, v) in enumerate(bands.items()):
            ax.plot(centers, v, color=SLOTS[i], marker=MARKERS[i], ms=8, lw=2, label=f"{t}: {DESCR.get(t, '')}")
        style(ax, f"Плотность шума по поддиапазонам, тон {f0:.0f} МГц\n"
                  f"(несущая, постоянная составляющая и HD2…HD10 исключены)",
              "плотность шума, dBc/Hz", "центр поддиапазона, МГц")
        ax.legend(fontsize=7.5, frameon=False, loc="upper left", bbox_to_anchor=(0, -0.23), ncol=1)
        fig.tight_layout(); fig.savefig(os.path.join(res, "shuffle_bands.png"), dpi=DPI,
                                        bbox_inches="tight", pad_inches=0.02); plt.close(fig)

        hdr = " | ".join(f"{i * step:.0f}-{(i + 1) * step:.0f}" for i in range(NBANDS))
        out += [f"Плотность шума по поддиапазонам (МГц), тон {f0:.0f} МГц, dBc/Hz:", "",
                f"| сценарий | {hdr} |", "|---|" + "---|" * NBANDS]
        for t, v in bands.items():
            out.append(f"| {t} | " + " | ".join(f"{x:.1f}" for x in v) + " |")
        out += ["", "![поддиапазоны](shuffle_bands.png)", ""]
    return out


# ---------------------------------------------------------------- seed study
def seed_section(res):
    """SEEDSTUDY=1: медианы по SEED для каждого режима перемешивания."""
    p = os.path.join(res, "seeds.csv")
    if not os.path.exists(p):
        return []
    d = pd.read_csv(p).drop_duplicates(["tag", "tones", "m1", "m2"], keep="last")
    d["mode"] = d.tag.str.replace(r"_s\d+$", "", regex=True)
    d["seed"] = d.tag.str.extract(r"_s(\d+)$")[0].astype(float)
    col = snr_col(d)
    one, two = d[d.tones == 1], d[d.tones == 2]
    modes = [m for m in SEED_MODES if m in set(d["mode"])]
    nseed = int(d.seed.nunique())

    out = [f"## Разброс по микросхемам: {nseed} наборов рассогласования (один SEED = одна микросхема)", ""]
    pr = os.path.join(res, "seeds_ref.csv")
    if os.path.exists(pr):
        r = pd.read_csv(pr).drop_duplicates(["tag", "tones", "m1", "m2"], keep="last")
        j = d.merge(r, on=["tag", "tones", "m1", "m2"], suffixes=("", "_ref"))
        dev = max((np.nanmax(np.abs(pd.to_numeric(j[c], errors="coerce") - pd.to_numeric(j[c + "_ref"], errors="coerce")))
                   for c in ["sfdr_dbc", "imd3_dbc"] if c in j and j[c].notna().any()), default=np.nan)
        out += [f"Проверка цепочки (seeds): max |измерено − model_ref| = {dev:.3f} дБ "
                f"на {len(j)} точках ({'OK' if dev < 0.05 else 'РАСХОЖДЕНИЕ'})", ""]

    def stat(v):
        v = pd.to_numeric(v, errors="coerce").dropna()
        return f"{v.median():.1f} ({v.min():.1f}\u2026{v.max():.1f})" if len(v) else ""

    f1 = one.fout_mhz.median() if len(one) else np.nan
    f2 = two.fout_mhz.median() if len(two) else np.nan
    out += [f"Медиана (мин…макс). SFDR и SNR: однотон {f1:.0f} МГц, −7 dBFS; "
            f"IMD3: двухтон {f2:.0f} МГц.", "",
            "| режим | SFDR, dBc | SNR, дБ | HD2, dBc | HD3, dBc | IMD3, dBc |",
            "|---|---|---|---|---|---|"]
    for m in modes:
        a, b = one[one["mode"] == m], two[two["mode"] == m]
        out.append(f"| {m} | {stat(a.sfdr_dbc)} | {stat(a[col]) if col else ''} | {stat(a.hd2_dbc)} | "
                   f"{stat(a.hd3_dbc)} | {stat(b.imd3_dbc)} |")
    out.append("")

    panels = [("SFDR, dBc", one, "sfdr_dbc"), ("SNR, дБ", one, col), ("IMD3, dBc", two, "imd3_dbc")]
    panels = [pp for pp in panels if pp[2] and len(pp[1])]
    if panels:
        fig, axs = plt.subplots(1, len(panels), figsize=(FIGW, 3.3))
        axs = np.atleast_1d(axs)
        rng = np.random.default_rng(0)
        for ax, (ttl, dd, c) in zip(axs, panels):
            for i, m in enumerate(modes):
                v = pd.to_numeric(dd[dd["mode"] == m][c], errors="coerce").dropna()
                ax.scatter(i + rng.uniform(-0.15, 0.15, len(v)), v, color=SLOTS[i], s=18)
                if len(v):
                    ax.hlines(v.median(), i - 0.3, i + 0.3, color=INK, lw=1.5)
            # four long mode names do not fit side by side in a narrow panel
            ax.set_xticks(range(len(modes)), modes, rotation=30, ha="right", fontsize=7)
            style(ax, ttl, "", "")
        fig.suptitle(f"{nseed} случайных наборов рассогласования сегментов; линия - медиана",
                     fontsize=10, color=INK)
        fig.tight_layout(); fig.savefig(os.path.join(res, "seeds.png"), dpi=DPI,
                                        bbox_inches="tight", pad_inches=0.02); plt.close(fig)
        out += ["![разброс по SEED](seeds.png)", ""]
    return out


# ---------------------------------------------------------------- main tables / plots
def plot(df, col, ds, ylabel, title, path, tones):
    d = df[df.tones == tones]
    if d.empty:
        return
    fig, ax = plt.subplots(figsize=(FIGW, 5.0))
    groups = list(d.groupby("tag", sort=False))
    for i, (tag, g) in enumerate(groups):
        g = g.sort_values("fout_mhz")
        # identical curves (e.g. dnl and full) would hide each other: later series drawn smaller
        ax.plot(g.fout_mhz, g[col], color=SLOTS[i % 8], marker=MARKERS[i % 8], ms=max(9 - i * 0.6, 4), lw=2,
                label=f"{tag}: {DESCR.get(tag, '')}", zorder=3 + i)
    ax.plot(list(ds), list(ds.values()), color=INK, marker="*", ms=12, lw=1.2, ls="--",
            label="даташит AD9081, Table 16 (перемешивание включено)", zorder=10)
    style(ax, title, ylabel)
    ax.legend(fontsize=7.5, frameon=False, loc="upper left", bbox_to_anchor=(0, -0.21), ncol=1)
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)


def main():
    res = sys.argv[1] if len(sys.argv) > 1 else "results"
    meas = pd.read_csv(os.path.join(res, "results.csv"))
    ref_p = os.path.join(res, "reference.csv")
    ref = pd.read_csv(ref_p) if os.path.exists(ref_p) else None
    meas = meas.drop_duplicates(["tag", "tones", "m1", "m2"], keep="last")
    order = list(dict.fromkeys(meas.tag))
    col = snr_col(meas)

    nl = meas[~meas.tag.map(is_jit)]
    plot(nl, "sfdr_dbc", DS_SFDR, "SFDR, dBc", "Однотон, −7 dBFS: SFDR",
         os.path.join(res, "sfdr_vs_fout.png"), 1)
    plot(nl, "imd3_dbc", DS_IMD3, "IMD3, dBc", "Двухтон, −6 dBFS на тон: IMD3",
         os.path.join(res, "imd3_vs_fout.png"), 2)

    out = ["# Нелинейность ЦАП: измерения (цепочка GNU Radio) рядом с Table 16 AD9081", ""]
    if ref is not None:
        ref = ref.drop_duplicates(["tag", "tones", "m1", "m2"], keep="last")
        k = ["tag", "tones", "m1", "m2"]
        j = meas.merge(ref, on=k, suffixes=("", "_ref"))
        cols = ["sfdr_dbc", "hd2_dbc", "hd3_dbc", "imd3_dbc"] + ([col] if col else [])
        dev = max((np.nanmax(np.abs(pd.to_numeric(j[c], errors="coerce") -
                                    pd.to_numeric(j[c + "_ref"], errors="coerce")))
                   for c in cols if c in j and j[c].notna().any()), default=np.nan)
        out += [f"Проверка цепочки: max |измерено − model_ref| = {dev:.3f} дБ на {len(j)} точках "
                f"({'OK' if dev < 0.05 else 'РАСХОЖДЕНИЕ - проверь wrapper, File Sink, SKIP, PIPE, DELAY'})", ""]

    s = meas[(meas.tones == 1) & ~meas.tag.map(is_jit)]
    if not s.empty:
        out += ["## Однотон, −7 dBFS", "",
                "| сценарий | fOUT, МГц | SFDR, dBc | худший спур | HD2, dBc | HD3, dBc | SNR, дБ | NSD, dBc/Hz | SFDR Table 16 |",
                "|---|---|---|---|---|---|---|---|---|"]
        for tag in order:
            for _, r in s[s.tag == tag].sort_values("fout_mhz").iterrows():
                dsv = DS_SFDR.get(int(round(r.fout_mhz / 10.0) * 10), "")
                spur = r.spur_label if isinstance(r.spur_label, str) else \
                    (f"{int(r.spur_bin) * FDAC_HZ / NFFT / 1e6:.0f} МГц" if pd.notna(r.get("spur_bin")) else "")
                out.append(f"| {tag} | {r.fout_mhz:.0f} | {r.sfdr_dbc:.1f} | {spur} "
                           f"| {db(r.hd2_dbc)} | {db(r.hd3_dbc)} | {num(r.get(col)) if col else ''} "
                           f"| {num(r.get('nsd_dbc_hz'))} | {dsv} |")
        out.append("")
    t = meas[meas.tones == 2]
    if not t.empty:
        out += ["## Двухтон, −6 dBFS на тон", "",
                "| сценарий | fc, МГц | IMD3 2f1−f2 | IMD3 2f2−f1 | IMD3 худший, dBc | IMD3 Table 16 |",
                "|---|---|---|---|---|---|"]
        for tag in order:
            for _, r in t[t.tag == tag].sort_values("fout_mhz").iterrows():
                dsv = DS_IMD3.get(int(round(r.fout_mhz / 100.0) * 100), "")
                out.append(f"| {tag} | {r.fout_mhz:.0f} | {db(r.imd3_lo_dbc)} | {db(r.imd3_hi_dbc)} | {db(r.imd3_dbc)} | {dsv} |")
        out.append("")
    out += ["![SFDR](sfdr_vs_fout.png)", "", "![IMD3](imd3_vs_fout.png)", ""]
    out += stage1_section(meas, res)
    out += shuffle_section(meas, res)
    out += seed_section(res)
    out += jitter_section(meas, res)
    with open(os.path.join(res, "summary.md"), "w") as f:
        f.write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()