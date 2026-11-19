#!/usr/bin/env python3
"""Rerun with the Rich Solar RS-M50 datasheet values (Voc 20.8 V, Isc 3.13 A, Vmp 17.6 V, Imp 2.84 A, 30 cells)."""
import os, numpy as np
import power_sim as ps
ps.PANEL.update(voc=20.8, isc=3.13, ns=30, tc_voc=-0.0028, tc_isc=0.00045, rsh=1000.0)
v = np.linspace(0, 30, 3001)
# fit ideality and series resistance to the datasheet maximum-power point
best = None
for n in np.arange(1.0, 1.61, 0.02):
    for rs in np.arange(0.0, 0.61, 0.02):
        ps.PANEL.update(n=n, rs=rs)
        i = ps.panel_iv(25, 1.0, v); p = v * i; k = np.argmax(p)
        err = (v[k] - 17.6) ** 2 + (p[k] - 50.0) ** 2 / 9
        if best is None or err < best[0]: best = (err, n, rs, v[k], p[k])
_, n, rs, vm, pm = best
ps.PANEL.update(n=float(n), rs=float(rs))
out = [f"RS-M50 fit: n={n:.2f}, Rs={rs:.2f} ohm -> Vmp {vm:.1f} V, Pmp {pm:.1f} W at STC",
       "cell C | sun | Voc V | Vmp V | Pmp W"]
for t in (-10, 25, 75):
    for g in (1.0, 0.1, 0.05):
        i = ps.panel_iv(t, g, v); p = v * i
        out.append(f"{t} | {g:.2f} | {v[np.argmax(i < 0)]:.1f} | {v[np.argmax(p)]:.1f} | {p.max():.1f}")
out.append("cell C | EN on/off V | 3 W load stays up from (% sun) | on/off cycles before that")
for t in (-10, 25, 75):
    for en in ((13.0, 11.0), (12.0, 10.0)):
        body = (f"Vg g 0 PWL(0 0 {ps.DAWN_T} 0.3)\n" + ps.panel_lines(t) + ps.buck_lines(*en) + ps.load_lines())
        d = ps.run("rs_m50_tmp", body, ps.DAWN_T, "20u", ["v(in)", "v(out)", "v(lden)"], maxstep="20u")
        sun = d["time"] / ps.DAWN_T * 30
        st = (d["vlden"] > 0.5).astype(int); on = np.where(np.diff(st) > 0)[0]
        out.append(f"{t} | {en[0]}/{en[1]} | {sun[on[-1]] if len(on) and st[-1] else float('nan'):.1f} | {len(on)}")
os.remove(os.path.join(ps.OUT, "rs_m50_tmp.cir"))
open(os.path.join(ps.OUT, "rs_m50.txt"), "w").write("\n".join(out) + "\n")
print("\n".join(out))
