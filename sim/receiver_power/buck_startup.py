#!/usr/bin/env python3
"""Start-up of the receiver buck into 22 uF plus three LC rail filters, using TPS62065 datasheet limits.

Generic averaged current-mode model, not the vendor model. Datasheet figures used: reference ramp 250 us,
current limit 2.3 A minimum, one third of that until VOUT passes one third of nominal. Capacitors derated
(18 uF, 23 uF). Loads are resistors (pessimistic early in the ramp). Two integrator behaviours bracket the
real part: frozen while in current limit (no wind-up) and free-running (full wind-up).
"""
import os, subprocess, numpy as np
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
LOADS = (0.156, 0.182, 0.060)

def run(cd, windup, ilim=2.3, tramp=250e-6):
    kp = 2 * np.pi * 150e3 * 18e-6; ki = kp * 2 * np.pi * 30e3
    n = f"""* buck start-up
Vref ref 0 PWL(0 0 50u 0 {50e-6+tramp/0.9} 3.35)
Blim lim 0 V = V(o) < 1.117 ? {ilim/3} : {ilim}
Braw raw 0 V = {kp}*(V(ref)-V(o)) + V(xi)
Bint 0 xi I = {'1' if windup else '((V(raw) < V(lim)) || (V(ref) < V(o)) ? 1 : 0)'} * {ki}*(V(ref)-V(o))
Cint xi 0 1 ic=0
Rint xi 0 1g
Bbuck 0 o I = min(V(lim), max(0, V(raw)))
C3 o 0 18u ic=0
"""
    for k, i in enumerate(LOADS):
        n += (f"L{k} o a{k} 2.2u ic=0\nRdcr{k} a{k} r{k} 0.084\nC{k} r{k} 0 18u ic=0\n"
              f"Cd{k} r{k} d{k} {cd} ic=0\nRd{k} d{k} 0 0.5\nRl{k} r{k} 0 {3.3/i}\n")
    n += (".options method=gear\n.control\nset wr_singlescale\nset wr_vecnames\ntran 0.2u 1.5m 0 0.2u uic\n"
          f"wrdata {OUT}/s.txt v(o) v(r1) v(ref)\n.endc\n.end\n")
    p = f"{OUT}/buck_startup_cd{cd*1e6:g}u_{'windup' if windup else 'frozen'}.cir"
    open(p, "w").write(n); subprocess.run(["ngspice", "-b", p], capture_output=True)
    d = np.genfromtxt(f"{OUT}/s.txt", names=True); os.remove(f"{OUT}/s.txt")
    return d

rep = ["damper capacitance (effective) | integrator | time to 95 % us | peak at buck output V | peak on 3.3V_SYNTH V | lag behind reference at end of ramp V"]
res = {}
for cd in (23e-6, 11e-6):
    for w in (False, True):
        d = run(cd, w); t = d["time"]
        t95 = t[np.argmax(d["vr1"] > 0.95 * 3.335)] - 50e-6
        k = np.argmin(np.abs(t - (50e-6 + 250e-6 / 0.9)))
        rep.append(f"{cd*1e6:.0f} uF | {'free' if w else 'frozen in limit'} | {t95*1e6:.0f} | {d['vo'].max():.2f} | {d['vr1'].max():.2f} | {3.35 - d['vo'][k]:.2f}")
        res[(cd, w)] = d
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
plt.rcParams.update({"figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": "#e8e7e2", "lines.linewidth": 2})
fig, ax = plt.subplots(figsize=(8, 4.2)); d = res[(23e-6, True)]; t = d["time"] * 1e6
ax.plot(t, d["vref"], color="#52514e", lw=1, ls="--", label="internal reference ramp")
ax.plot(t, d["vo"], color="#2a78d6", label="buck output")
ax.plot(t, d["vr1"], color="#1baf7a", label="3.3V_SYNTH after its filter")
ax.axhline(3.6, color="#52514e", lw=1); ax.text(1490, 3.63, "3.6 V absolute maximum of the 3.3 V parts", ha="right", fontsize=9, color="#52514e")
ax.set_xlabel("Time (us)"); ax.set_ylabel("Voltage (V)"); ax.legend(frameon=False, loc="lower right")
ax.set_title("Receiver buck start-up, worst case: minimum current limit, full integrator wind-up", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig(f"{OUT}/buck_startup.png", dpi=200)
open(f"{OUT}/buck_startup.txt", "w").write("\n".join(rep) + "\n"); print("\n".join(rep))
