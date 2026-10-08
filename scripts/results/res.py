import re
import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# Input
# ============================================================

INPUT_FILE = "summary.txt"

with open(INPUT_FILE, "r") as f:
    text = f.read()

# ============================================================
# Parse:
#   --- AW=12 DW=14 ---
#
#   DW=14: mean 80.37 | min 80.37 | max 80.37 dBc
# ============================================================

pattern = re.compile(
    r'---\s*AW=(\d+)\s+DW=(\d+)\s*---.*?'
    r'DW=\d+:\s*mean\s+([\d.]+)',
    re.S
)

data = []

for aw, dw, sfdr in pattern.findall(text):
    data.append((int(aw), int(dw), float(sfdr)))

if not data:
    raise RuntimeError("Не удалось найти данные")

# ============================================================
# Convert to arrays
# ============================================================

aws = sorted(set(x[0] for x in data))
dws = sorted(set(x[1] for x in data))

sfdr = np.full((len(aws), len(dws)), np.nan)

for aw, dw, value in data:
    i = aws.index(aw)
    j = dws.index(dw)
    sfdr[i, j] = value

print("AW:", aws)
print("DW:", dws)
print("\nSFDR [dBc]:")
print(sfdr)

# ============================================================
# 1. Heatmap: SFDR(AW, DW)
# ============================================================

fig, ax = plt.subplots(figsize=(8, 6))

im = ax.imshow(
    sfdr,
    origin="lower",
    aspect="auto",
    interpolation="nearest"
)

ax.set_xticks(range(len(dws)))
ax.set_xticklabels(dws)

ax.set_yticks(range(len(aws)))
ax.set_yticklabels(aws)

ax.set_xlabel("DW (DAC width), bits")
ax.set_ylabel("AW (ROM address width), bits")
ax.set_title("SFDR vs AW / DW")

cbar = fig.colorbar(im, ax=ax)
cbar.set_label("SFDR, dBc")

# Values inside cells
for i in range(len(aws)):
    for j in range(len(dws)):
        if not np.isnan(sfdr[i, j]):
            ax.text(
                j, i,
                f"{sfdr[i, j]:.2f}",
                ha="center",
                va="center"
            )

plt.tight_layout()
plt.savefig("sfdr_aw_dw_heatmap.png", dpi=200)
plt.show()

# ============================================================
# 2. SFDR vs DW for each AW
# ============================================================

fig, ax = plt.subplots(figsize=(8, 6))

for i, aw in enumerate(aws):
    ax.plot(
        dws,
        sfdr[i, :],
        marker="o",
        label=f"AW={aw}"
    )

ax.set_xlabel("DW (DAC width), bits")
ax.set_ylabel("SFDR, dBc")
ax.set_title("SFDR vs DW")
ax.grid(True)
ax.legend()

plt.tight_layout()
plt.savefig("sfdr_vs_dw.png", dpi=200)
plt.show()

# ============================================================
# 3. SFDR vs AW for each DW
# ============================================================

fig, ax = plt.subplots(figsize=(8, 6))

for j, dw in enumerate(dws):
    ax.plot(
        aws,
        sfdr[:, j],
        marker="o",
        label=f"DW={dw}"
    )

ax.set_xlabel("AW (ROM address width), bits")
ax.set_ylabel("SFDR, dBc")
ax.set_title("SFDR vs AW")
ax.grid(True)
ax.legend()

plt.tight_layout()
plt.savefig("sfdr_vs_aw.png", dpi=200)
plt.show()