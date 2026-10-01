import math 
AW, DW = 14, 16
with open("sine.hex", "w") as f:
    for i in range(1 << AW):
        v = round((2**(DW-1) - 1) * math.sin(2*math.pi * i / (1 << AW)))
        f.write(f"{v & ((1 << DW) - 1):04x}\n")