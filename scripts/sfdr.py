#!/usr/bin/env python3
"""
SFDR / HD2 / HD3 (single tone) and IMD3 (two tones) of a coherent DDS/DAC record.

Coherent sampling only: tone k sits exactly on FFT bin M_k (M odd, NFFT = 2^LOG2N),
so a rectangular window is exact (no leakage, no window scalloping).

  fOUT = M / NFFT * fDAC          (fDAC = 12000 MHz by default -> AD9081 Table 16)

Levels: dBFS relative to full scale 2^BITS (BITS = DW-1+FRAC = 19 for DW=16, FRAC=4);
        spurs/harmonics in dBc relative to the carrier (two tones: the stronger tone, as in Table 16).

Examples
  python3 sfdr.py run.bin --m 2457                         # single tone
  python3 sfdr.py run.bin --m 2457 --m2 2459               # two tones -> IMD3
  python3 sfdr.py run.bin --m 2457 --csv results.csv --tag inl3 -v
"""
import argparse
import csv
import os

import numpy as np

NFFT = 32768
SKIP = 1000
FDAC_MHZ = 12000.0
N_HARM = 10
N_TOP = 8


def load(path, dtype="int32", skip=SKIP, nfft=NFFT):
    x = np.fromfile(path, dtype=dtype).astype(np.float64)
    if len(x) < skip + nfft:
        raise SystemExit(f"{path}: {len(x)} samples, need skip+nfft = {skip + nfft}")
    return x[skip:skip + nfft]


def spectrum(x, bits):
    """Single-sided amplitude spectrum in dBFS (rect window, coherent)."""
    n = len(x)
    a = np.abs(np.fft.rfft(x)) / (n / 2.0)
    a[0] /= 2.0
    return 20 * np.log10(np.maximum(a / float(2 ** bits), 1e-20))


def fold(b, n):
    b %= n
    return n - b if b > n // 2 else b


def _check_coherent(d, bins, n, label):
    for b in bins:
        side = max(d[(b - 1) % (n // 2 + 1)], d[(b + 1) % (n // 2 + 1)])
        if side - d[b] > -80:
            print(f"WARNING {label}: leakage around bin {b} ({side - d[b]:.1f} dBc) - "
                  f"record is not coherent (wrong M, SKIP or a transient in the record?)")


def measure_tone(x, bits, m, label="", verbose=False):
    n = len(x)
    d = spectrum(x, bits)
    if m % 2 == 0:
        print(f"WARNING {label}: M = {m} is even")
    _check_coherent(d, [m], n, label)
    car = d[m]
    harm = {fold(k * m, n): k for k in range(2, N_HARM + 1)}

    sp = d.copy()
    sp[0] = -np.inf                     # DC (bow INL adds a DC offset, not a spur)
    sp[m] = -np.inf
    s = int(np.argmax(sp))
    p =  10**(np.array(d)/10)
    mask = np.ones(len(p), dtype=bool)
    mask[0] = False
    mask[m] = False
    for h in harm.keys():
        mask[h] = False
    noise = p[mask].sum()
    snr_dB = 10*np.log10(p[m]/noise)
    nsd_dbc_hz = -snr_dB - 10*np.log10(FDAC_MHZ * 1e6 / 2)

    res = dict(tones=1, m1=m, m2="", fout_mhz=m / n * FDAC_MHZ, carrier_dbfs=car,
                sfdr_dbc=car - sp[s], spur_bin=s, spur_label=f"HD{harm[s]}" if s in harm else "",
                hd2_dbc=d[fold(2 * m, n)] - car, hd3_dbc=d[fold(3 * m, n)] - car,
                imd3_lo_dbc="", imd3_hi_dbc="", imd3_dbc="", snr_dB=snr_dB, nsd_dbc_hz=nsd_dbc_hz)
    if verbose:
        print(f"== {label}  single tone  M={m}  fOUT={res['fout_mhz']:.1f} MHz @ {FDAC_MHZ:.0f} MSPS")

        print(f"carrier {car:.2f} dBFS | SFDR {res['sfdr_dbc']:.2f} dBc (bin {s} {res['spur_label']}) SNR {res['snr_dB']:.2f} dB | NSD {res['nsd_dbc_hz']:.2f} dBc/Hz")
        for hb, k in sorted(harm.items(), key=lambda t: t[1]):
            print(f"  HD{k:<2d} bin {hb:6d}  {d[hb] - car:+8.2f} dBc")
        _top(sp, car, lambda b: f"HD{harm[b]}" if b in harm else "")
    return res


def measure_two(x, bits, m1, m2, label="", verbose=False):
    n = len(x)
    d = spectrum(x, bits)
    _check_coherent(d, [m1, m2], n, label)
    ref = max(d[m1], d[m2])
    lo, hi = fold(2 * m1 - m2, n), fold(2 * m2 - m1, n)
    names = {lo: "IMD3", hi: "IMD3", fold(3 * m1 - 2 * m2, n): "IMD5", fold(3 * m2 - 2 * m1, n): "IMD5",
             fold(2 * m1, n): "HD2", fold(2 * m2, n): "HD2", fold(m1 + m2, n): "f1+f2",
             fold(3 * m1, n): "HD3", fold(3 * m2, n): "HD3",
             fold(2 * m1 + m2, n): "2f1+f2", fold(2 * m2 + m1, n): "2f2+f1"}
    sp = d.copy()
    sp[0] = -np.inf
    sp[m1] = sp[m2] = -np.inf
    s = int(np.argmax(sp))

    res = dict(tones=2, m1=m1, m2=m2, fout_mhz=(m1 + m2) / 2 / n * FDAC_MHZ, carrier_dbfs=ref,
               sfdr_dbc=ref - sp[s], spur_bin=s, spur_label=names.get(s, ""),
               hd2_dbc="", hd3_dbc="",
               imd3_lo_dbc=d[lo] - ref, imd3_hi_dbc=d[hi] - ref, imd3_dbc=max(d[lo], d[hi]) - ref)
    if verbose:
        df = (m2 - m1) / n * FDAC_MHZ
        print(f"== {label}  two tones  M1={m1} M2={m2}  fc={res['fout_mhz']:.1f} MHz, spacing {df:.3f} MHz")
        print(f"tones {d[m1]:.2f} / {d[m2]:.2f} dBFS")
        print(f"IMD3 2f1-f2 {res['imd3_lo_dbc']:+.2f} dBc | 2f2-f1 {res['imd3_hi_dbc']:+.2f} dBc "
              f"| worst {res['imd3_dbc']:+.2f} dBc")
        print(f"worst spur (excluding tones) {res['sfdr_dbc']:.2f} dBc below, bin {s} {res['spur_label']}")
        _top(sp, ref, lambda b: names.get(b, ""))
    return res


def _top(sp, ref, lab):
    cand = np.where(np.isfinite(sp), sp, -400)
    idx = np.argsort(cand)[::-1]
    print("  top spurs:")
    for i, b in enumerate(idx[:N_TOP], 1):
        print(f"  {i:2d}: bin {b:6d} {cand[b] - ref:+8.2f} dBc {lab(b)}")


FIELDS = ["tag", "tones", "m1", "m2", "fout_mhz", "carrier_dbfs", "sfdr_dbc", "spur_bin", "spur_label",
        "hd2_dbc", "hd3_dbc", "imd3_lo_dbc", "imd3_hi_dbc", "imd3_dbc", "snr_dB", "nsd_dbc_hz", "file"]


def append_csv(path, row):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: (f"{v:.3f}" if isinstance(v, float) else v) for k, v in row.items() if k in FIELDS})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--m", type=int, required=True, help="tone 1 bin (odd)")
    ap.add_argument("--m2", type=int, help="tone 2 bin -> two-tone IMD3 measurement")
    ap.add_argument("--bits", type=int, default=19, help="full scale = 2^BITS (DW-1+FRAC)")
    ap.add_argument("--dtype", default="int32", choices=["int32", "float32", "int16"],
                    help="File Sink item type (sizeof_int -> int32)")
    ap.add_argument("--skip", type=int, default=SKIP)
    ap.add_argument("--nfft", type=int, default=NFFT)
    ap.add_argument("--fdac", type=float, default=12000.0, help="MHz, only for fOUT labels")
    ap.add_argument("--csv", help="append the result to this CSV")
    ap.add_argument("--tag", default="", help="scenario name written to the CSV")
    a = ap.parse_args()

    global FDAC_MHZ
    FDAC_MHZ = a.fdac
    x = load(a.file, a.dtype, a.skip, a.nfft)
    if np.max(np.abs(x)) >= 2 ** a.bits - 1:
        print(f"WARNING {a.file}: samples at full scale (clipping or wrong --bits?)")
    if a.m2 is None:
        r = measure_tone(x, a.bits, a.m, a.file, True)
    else:
        r = measure_two(x, a.bits, a.m, a.m2, a.file, True)
    if a.csv:
        r.update(tag=a.tag, file=os.path.basename(a.file))
        append_csv(a.csv, r)


if __name__ == "__main__":
    main()
