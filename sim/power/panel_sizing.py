#!/usr/bin/env python3
"""Panel sizing: at what sun fraction does the 3 W load stay up, by panel size, cell temperature and EN thresholds."""
import numpy as np
import power_sim as ps

def start_point(isc, tcell, en):
    ps.PANEL["isc"] = isc
    body = (f"Vg g 0 PWL(0 0 {ps.DAWN_T} 0.4)\n" + ps.panel_lines(tcell) + ps.buck_lines(*en) + ps.load_lines())
    d = ps.run("sizing_tmp", body, ps.DAWN_T, "20u", ["v(in)", "v(out)", "v(lden)"], maxstep="20u")
    sun = d["time"] / ps.DAWN_T * 40
    st = (d["vlden"] > 0.5).astype(int); on = np.where(np.diff(st) > 0)[0]
    return (sun[on[-1]] if len(on) and st[-1] else float("nan")), len(on)

rows = ["panel W | cell C | EN on/off V | load stays up from (% sun) | on/off cycles before that"]
for watts, isc in ((20, 1.2), (30, 1.8), (50, 3.0), (100, 6.0)):
    for t in (-10, 25, 75):
        for en in ((14.0, 12.5), (13.0, 11.0)):
            s, n = start_point(isc, t, en)
            rows.append(f"{watts} | {t} | {en[0]}/{en[1]} | {s:.1f} | {n}")
import os
os.remove(os.path.join(ps.OUT, "sizing_tmp.cir"))
open(os.path.join(ps.OUT, "panel_sizing.txt"), "w").write("\n".join(rows) + "\n")
print("\n".join(rows))
