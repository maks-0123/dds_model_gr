import sys, numpy as np
import model_ref as mr, sfdr

raw_path, params, m = sys.argv[1], sys.argv[2], int(sys.argv[3])
p = mr.parse_params(params)
n = 1 << p["LOG2N"]
skip = sfdr.SKIP
raw = np.fromfile(raw_path, dtype=np.int32)[skip:skip + n].astype(np.int64)

codes = mr.dds_codes(p, m, n + skip)          # DDS samples 0 .. n+skip-1
best = []
for pipe in range(0, 17):
    y = mr.dac(dict(p, PIPE=pipe), codes)      # shuffle sequence, draw index = j + pipe
    for k in range(0, 9):                      # raw[skip+i] = model[skip+i-k]
        cand = y[skip - k: skip - k + n]
        best.append(((cand == raw).mean(), pipe, k))
best.sort(reverse=True)
for frac, pipe, k in best[:5]:
    print(f"PIPE={pipe:2d}  K={k}  equal samples: {100*frac:.2f} %")