#!/usr/bin/env python3
"""
SFDR of single-tone records (float32 binary). One file per tone frequency.

coherent     : F0 = M*Fs/NFFT, M odd -> rectangular window
non-coherent : any F0                -> Blackman-Harris window

Examples
  python sfdr.py f_14_5189.bin --dw 14                    # M from 'M2457' / trailing '_2457' in the name, otherwise auto-detected
  python sfdr.py f_14_*.bin --dw 14                       # several files -> table + mean/min/max
  python sfdr.py a.bin b.bin --ms 5189 5191 --dw 14       # explicit M per file
  python sfdr.py f.bin --noncoherent --f0 2399.414 --dw 14 -v
"""
import argparse, re, os
import numpy as np
from scipy.signal import find_peaks
from scipy.signal.windows import blackmanharris

FS = 32000.0
NFFT = 32768
SKIP = 1000
N_HARM = 10
N_TOP = 10
DC_BINS = 4
NEAR_HZ = 100.0
NEAR_THRESH_DB = 6.0


def measure(path, dw, m=None, f0=None, coherent=True, verbose=False, plot=False, dtype='float32'):
    FULLSCALE = float(2 ** (dw - 1))
    x = np.fromfile(path, dtype=dtype).astype(np.float64)
    if len(x) < SKIP + NFFT:
        raise SystemExit(f"{path}: not enough samples ({len(x)}), need {SKIP + NFFT}")
    x = x[SKIP:SKIP + NFFT]

    if coherent:
        F0, MAIN, w, wname = (m * FS / NFFT if m else None), 1, np.ones(NFFT), "rect"
        if m and m % 2 == 0:
            print(f"WARNING {path}: M is even")
    else:
        F0, MAIN, w, wname = f0, 4, blackmanharris(NFFT), "blackman-harris"
        x = x - x.mean()
    if np.mean(np.abs(x) >= FULLSCALE - 1) > 0:
        print(f"WARNING {path}: samples at full scale (clipping or wrong --dw?)")

    X = np.fft.rfft(x * w)
    amp = np.abs(X) / (w.sum() / 2.0)
    amp[0] /= 2.0
    dbfs = 20 * np.log10(np.maximum(amp / FULLSCALE, 1e-20))
    freq = np.fft.rfftfreq(NFFT, 1.0 / FS)
    half = len(amp)

    # carrier: search around the expected bin, power over main lobe
    g = DC_BINS + int(np.argmax(amp[DC_BINS:]))          # strongest bin in the whole spectrum
    if F0 is None:
        F0 = g * FS / NFFT
        print(f"NOTE {path}: M not given, using strongest peak: bin {g} ({F0:.4f} Hz) -> M = {g}")
    f_exp = int(round(F0 * NFFT / FS))
    lo, hi = max(DC_BINS, f_exp - 5), min(half, f_exp + 6)
    f_bin = lo + int(np.argmax(amp[lo:hi]))
    if amp[g] > 10 * amp[f_bin]:                          # >20 dB stronger tone elsewhere
        print(f"WARNING {path}: no tone near {F0:.4f} Hz (bin {f_exp}); the strongest peak is at "
              f"{freq[g]:.4f} Hz (bin {g}, M = {g}). Using it as the carrier.")
        f_bin, F0 = g, g * FS / NFFT
    m_lo, m_hi = max(0, f_bin - MAIN), min(half, f_bin + MAIN + 1)
    carrier_amp = 2 * np.sqrt(np.sum(np.abs(X[m_lo:m_hi]) ** 2) / (NFFT * np.sum(w ** 2)))
    carrier_db = 20 * np.log10(carrier_amp / FULLSCALE)

    # spurs
    sp = dbfs.copy()
    sp[:DC_BINS] = -np.inf
    near_bins = int(np.ceil(NEAR_HZ / (FS / NFFT)))
    n_lo, n_hi = max(DC_BINS, f_bin - near_bins), min(half, f_bin + near_bins + 1)
    pk, _ = find_peaks(dbfs[n_lo:n_hi], prominence=NEAR_THRESH_DB)
    near_keep = {n_lo + p for p in pk if not (m_lo <= n_lo + p < m_hi)}
    sp[n_lo:n_hi] = -np.inf
    for b in near_keep:
        sp[b] = dbfs[b]
    sp[m_lo:m_hi] = -np.inf
    s_bin = int(np.argmax(sp))
    sfdr = carrier_db - sp[s_bin]

    # noise floor: mean power of all non-zero bins outside carrier/DC (includes spurs)
    mask = np.isfinite(sp)
    p = (amp[mask] / FULLSCALE) ** 2
    floor = 10 * np.log10(np.mean(p[p > 1e-24]))
    margin = sp[s_bin] - floor

    def fold(b):
        b %= NFFT
        return NFFT - b if b > NFFT // 2 else b
    harm = {fold(k * f_bin): k for k in range(2, N_HARM + 1)}
    tol = 1 if coherent else MAIN

    def label(b):
        for hb, k in harm.items():
            if abs(b - hb) <= tol:
                return f"HD{k}"
        return "near" if b in near_keep else ""

    if verbose:
        print("=" * 58)
        print(f"{path}  ({'coherent' if coherent else 'non-coherent'}, {wname}, DW={dw})")
        print(f"F0 requested {F0:.6f} Hz | measured {freq[f_bin]:.6f} Hz (bin {f_bin})")
        if not coherent:
            print(f"FTW (48-bit): 48'h{int(round(F0 / FS * 2 ** 48)):012x}")
        print(f"Carrier {carrier_db:.2f} dBFS | worst spur {freq[s_bin]:.4f} Hz {sp[s_bin]:.2f} dBFS {label(s_bin)}")
        print(f"SFDR {sfdr:.2f} dBc | floor {floor:.2f} dBFS/bin | spur above floor {margin:.1f} dB")
        print("\nTop spurs:")
        cand = np.where(np.isfinite(sp), sp, -300)
        pk2, _ = find_peaks(cand)
        for i, b in enumerate(pk2[np.argsort(cand[pk2])[::-1]][:N_TOP], 1):
            print(f"{i:2d}: {freq[b]:10.4f} Hz {sp[b]-carrier_db:+8.2f} dBc {label(b)}")
        print("\nHarmonics:")
        for hb, k in sorted(harm.items(), key=lambda t: t[1]):
            print(f"HD{k:<2d}: {freq[hb]:10.4f} Hz {dbfs[hb]-carrier_db:+8.2f} dBc")
        print("=" * 58)
    if plot:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(11, 5))
        plt.plot(freq, dbfs, lw=0.7)
        plt.plot(freq[s_bin], dbfs[s_bin], "rv", label=f"SFDR {sfdr:.1f} dBc")
        plt.xlabel("Hz"); plt.ylabel("dBFS"); plt.grid(True); plt.legend(); plt.show()

    return dict(path=path, m=m, f0=freq[f_bin], carrier=carrier_db, sfdr=sfdr,
                spur_f=freq[s_bin], label=label(s_bin), margin=margin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--dw", type=int, default=16, help="DAC width, full scale = 2^(DW-1)")
    ap.add_argument("--ms", type=int, nargs="*", help="odd M per file (default: last number in file name)")
    ap.add_argument("--noncoherent", action="store_true")
    ap.add_argument("--f0", type=float, help="Hz, for --noncoherent")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--dtype", default="float32", choices=["float32", "int32", "int16"],
                    help="sample type in the file (File Sink item size: float=float32, int=int32)")
    a = ap.parse_args()

    if a.noncoherent:
        if a.f0 is None:
            ap.error("--noncoherent needs --f0")
        ms = [None] * len(a.files)
    elif a.ms:
        if len(a.ms) != len(a.files):
            ap.error("--ms must have one value per file")
        ms = a.ms
    else:
        ms = []
        for f in a.files:
            stem = os.path.splitext(os.path.basename(f))[0]
            mm = re.findall(r"[Mm](\d+)", stem) or re.findall(r"_(\d+)$", stem)
            ms.append(int(mm[-1]) if mm else None)      # None -> auto-detect the tone

    res = [measure(f, a.dw, m=m, f0=a.f0, coherent=not a.noncoherent,
                   verbose=a.verbose or len(a.files) == 1, plot=a.plot, dtype=a.dtype)
           for f, m in zip(a.files, ms)]

    if len(res) > 1:
        print(f"\n{'file':32s} {'M':>6s} {'F0,Hz':>10s} {'SFDR,dBc':>9s} {'spur':>6s} {'>floor,dB':>9s}")
        for r in res:
            print(f"{os.path.basename(r['path']):32s} {str(r['m']):>6s} {r['f0']:10.3f} {r['sfdr']:9.2f} {r['label']:>6s} {r['margin']:9.1f}")
        s = np.array([r["sfdr"] for r in res])
        print(f"\nDW={a.dw}: mean {s.mean():.2f} | min {s.min():.2f} | max {s.max():.2f} dBc  ({len(s)} runs)")


if __name__ == "__main__":
    main()