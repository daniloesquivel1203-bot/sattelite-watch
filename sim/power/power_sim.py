#!/usr/bin/env python3
"""First-pass system-level power simulation for the satellite tracker.

Averaged (non-switching) behavioural models in ngspice. Every number marked
ASSUMED is a placeholder until the schematic and parts threads confirm it.

Usage: python3 power_sim.py   (needs ngspice, numpy, matplotlib)
"""
import math, os, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

# ---------------- ASSUMED inputs ----------------
PANEL = dict(voc=22.0, isc=3.0, ns=36, n=1.3, rs=0.25, rsh=1000.0,  # generic 50 W "12 V" panel at STC
             tc_voc=-0.0029, tc_isc=0.0005)
CELL_TEMPS = {"cold, cell at -1 C": -1.0, "STC, cell at 25 C": 25.0, "hot, cell at 75 C": 75.0}
P_LOAD = 3.0        # W on the 5 V rail (design figure from the plan; estimate is 2.3 W)
ETA = 0.90          # buck efficiency, ASSUMED
ILIM = 3.5          # A, buck average output current limit, ASSUMED (LMR51430 is a 3 A part)
VIN_ON, VIN_OFF = 4.3, 3.9   # V, buck input UVLO with no EN divider, ASSUMED
RAIL_ON, RAIL_OFF = 4.5, 3.7 # V, 5 V rail supervisor thresholds for the load, ASSUMED
CIN, COUT = 100e-6, 47e-6


def panel_lines(tcell, gnode="g"):
    p = PANEL
    k = 8.617e-5
    nvt = p["ns"] * p["n"] * k * (tcell + 273.15)
    voc = p["voc"] * (1 + p["tc_voc"] * (tcell - 25))
    isc = p["isc"] * (1 + p["tc_isc"] * (tcell - 25))
    i0 = isc / math.exp(voc / nvt)
    # diode written as a B source so the panel temperature is independent of the ngspice TEMP
    return f"""
Bph 0 pvx I = {isc}*V({gnode})
Bd pvx 0 I = {i0}*(exp(min(V(pvx),40)/{nvt})-1)
Rsh pvx 0 {p['rsh']}
Rs pvx in {p['rs']}
"""


def buck_lines(en_on=VIN_ON, en_off=VIN_OFF, vset=5.0):
    return f"""
Cin in 0 {CIN} ic=0
* enable comparator with hysteresis
Benx enx 0 V = V(in) > (V(en) > 0.5 ? {en_off} : {en_on}) ? 1 : 0
Ren enx en 1k
Cen en 0 10n ic=0
* 4 ms soft start
Rss enx ss 4k
Css ss 0 1u ic=0
* averaged buck: regulates V(out), current limited, cannot exceed 97 % duty
Bictl ictl 0 V = V(en) > 0.5 ? min({ILIM}, max(0, 50*({vset}*V(ss) - V(out)))) * min(1, max(0, 20*(0.97*V(in) - V(out)))) : 0
Bout 0 out I = V(ictl)
Bin in 0 I = V(en) > 0.5 ? V(out)*V(ictl)/({ETA}*max(V(in),1)) + 100u : 5u
Cout out 0 {COUT} ic=0
"""


def load_lines(p=P_LOAD, node="out"):
    return f"""
* constant-power load behind a rail supervisor
Bldx ldx 0 V = V({node}) > (V(lden) > 0.5 ? {RAIL_OFF} : {RAIL_ON}) ? 1 : 0
Rld ldx lden 1k
Cld lden 0 10n ic=0
Bload {node} 0 I = V(lden) > 0.5 ? {p}/max(V({node}),1) : 0
"""


def run(name, body, tstop, tstep, nodes, maxstep=None):
    raw = os.path.join(OUT, name + ".txt")
    net = os.path.join(OUT, name + ".cir")
    ms = f" 0 {maxstep}" if maxstep else ""
    with open(net, "w") as f:
        f.write(f"* {name}\n{body}\n.options reltol=2e-3 abstol=1e-7 vntol=1e-5 method=gear\n"
                f".control\nset wr_singlescale\nset wr_vecnames\ntran {tstep} {tstop}{ms} uic\n"
                f"wrdata {raw} {' '.join(nodes)}\n.endc\n.end\n")
    r = subprocess.run(["ngspice", "-b", net], capture_output=True, text=True)
    if not os.path.exists(raw):
        sys.exit(f"{name} failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    d = np.genfromtxt(raw, names=True)
    os.remove(raw)
    return d


# ---------- 1. panel curves (closed form from the same model) ----------
def panel_iv(tcell, g, v):
    p = PANEL; k = 8.617e-5
    nvt = p["ns"] * p["n"] * k * (tcell + 273.15)
    voc = p["voc"] * (1 + p["tc_voc"] * (tcell - 25))
    isc = p["isc"] * (1 + p["tc_isc"] * (tcell - 25))
    i0 = isc / math.exp(voc / nvt)
    i = np.full_like(v, isc * g)
    for _ in range(200):  # fixed-point on series resistance
        vd = v + i * p["rs"]
        i = 0.5 * i + 0.5 * (isc * g - i0 * (np.exp(np.minimum(vd, 40) / nvt) - 1) - vd / p["rsh"])
    return i


def panel_table():
    v = np.linspace(0, 26, 2601)
    rows = []
    for label, t in CELL_TEMPS.items():
        for g in (1.0, 0.2, 0.1, 0.05):
            i = panel_iv(t, g, v); pw = v * i
            voc = v[np.argmax(i < 0)] if (i < 0).any() else float("nan")
            rows.append((label, g, voc, v[np.argmax(pw)], pw.max()))
        # smallest sun fraction that carries the load
        need = P_LOAD / ETA
        gs = np.linspace(0.01, 0.5, 491)
        gmin = next(g for g in gs if (v * panel_iv(t, g, v)).max() >= need)
        rows.append((label, "min for %.1f W" % P_LOAD, float("nan"), float("nan"), gmin))
    return rows


# ---------- 2. dawn ramp, no storage ----------
DAWN_T, DAWN_G = 3.0, 0.30
EN_DIV = (14.0, 12.5)   # V, turn-on / turn-off set by an EN divider, ASSUMED achievable with the LMR51430 EN pin

def dawn(name, en=None):
    bl = buck_lines(*en) if en else buck_lines()
    body = f"Vg g 0 PWL(0 0 {DAWN_T} {DAWN_G})\n" + panel_lines(25) + bl + load_lines()
    return run(name, body, DAWN_T, "20u", ["v(in)", "v(out)", "v(lden)"], maxstep="20u")


# ---------- 3. hold-up: panel blacks out, supercap on the 5 V rail ----------
def holdup(c, esr=0.05, p=P_LOAD):
    body = (f"Csc sc 0 {c} ic=5\nResr sc out {esr}\nCout out 0 {COUT} ic=5\n"
            f"Bload out 0 I = {p}/max(V(out),2)\n")
    d = run(f"holdup_{c:g}F", body, 100, "10m", ["v(out)"], maxstep="50m")
    t = d["time"]; v = d["vout"]
    below = np.argmax(v <= RAIL_OFF + 1e-3)
    return t, v, (t[below] if below else float("nan"))


# ---------- 4. charging a supercap from empty ----------
def charge(g, c=10.0, limited=None, tstop=120, maxstep="5m"):
    """limited=None: supercap straight on the buck output. limited=amps: through a current-limited charger."""
    body = f"Vg g 0 {g}\n" + panel_lines(25) + buck_lines()
    if limited is None:
        body += f"Csc sc 0 {c} ic=0\nResr sc out 0.05\n"
    else:
        body += (f"Csc sc 0 {c} ic=0\nResr sc scx 0.05\n"
                 f"Bchg out scx I = V(out) > 4.6 ? min({limited}, max(0, 10*(V(out)-V(scx)))) : 0\n")
    return run(f"charge_g{g:g}_{'direct' if limited is None else 'lim'}", body, tstop, "1m",
               ["v(in)", "v(out)", "v(sc)", "v(en)"], maxstep=maxstep)


if __name__ == "__main__":
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    INK, MUTED, SURF = "#0b0b0b", "#52514e", "#fcfcfb"
    C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
    plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": "#c9c8c2",
                         "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                         "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.color": "#e8e7e2", "font.size": 10, "lines.linewidth": 2})
    rep = []
    rep.append("PANEL (generic 50 W, 36 cells, ASSUMED)\ncondition | sun fraction | Voc V | Vmp V | Pmp W")
    for r in panel_table():
        if isinstance(r[1], str):
            rep.append(f"{r[0]} | {r[1]}: needs {r[4]*100:.0f} % of full sun")
        else:
            rep.append(f"{r[0]} | {r[1]:.2f} | {r[2]:.1f} | {r[3]:.1f} | {r[4]:.1f}")

    fig, ax = plt.subplots(2, 2, figsize=(10, 5.2), sharex=True, sharey="row")
    rep.append("\nDAWN, no storage, sun ramped 0 to %d %% (compressed into %g s)" % (DAWN_G*100, DAWN_T))
    for j, (title, name, en) in enumerate([("Buck starts at its own 4.3 V UVLO", "dawn_uvlo_only", None),
                                           ("EN divider: on at %g V, off at %g V" % EN_DIV, "dawn_en_divider", EN_DIV)]):
        d = dawn(name, en)
        sun = d["time"] / DAWN_T * DAWN_G * 100
        ax[0, j].plot(sun, d["vin"], color=C[0], lw=1); ax[1, j].plot(sun, d["vout"], color=C[1], lw=1)
        ax[0, j].set_title(title, loc="left", fontsize=10); ax[1, j].set_xlabel("Sunlight (% of full sun)")
        st = (d["vlden"] > 0.5).astype(int); on = np.where(np.diff(st) > 0)[0]
        stable = sun[on[-1]] if len(on) and st[-1] else float("nan")
        rep.append(f"{title}: load switched on {len(on)} times; rail stays up from {stable:.1f} % sun")
    ax[0, 0].set_ylabel("Panel voltage (V)"); ax[1, 0].set_ylabel("5 V rail (V)")
    fig.suptitle("Dawn with no storage: where the 3 W load finally stays on", x=0.01, ha="left", fontsize=12)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "dawn_no_storage.png"), dpi=200); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.2))
    rep.append("\nHOLD-UP on the 5 V rail, 5.0 V down to %.1f V, %.1f W load\nC (F) | seconds" % (RAIL_OFF, P_LOAD))
    for c, col in zip((5, 10, 25, 50), C):
        t, v, th = holdup(c)
        m = v >= RAIL_OFF
        ax.plot(t[m], v[m], color=col, label=f"{c} F: {th:.0f} s")
        rep.append(f"{c} | {th:.1f}")
    ax.axhline(RAIL_OFF, color=MUTED, lw=1, ls="--"); ax.set_ylim(3.5, 5.1); ax.text(99, RAIL_OFF - 0.09, "load cut-off (assumed 3.7 V)", ha="right", color=MUTED, fontsize=9)
    ax.set_xlabel("Time after the panel output is lost (s)"); ax.set_ylabel("5 V rail (V)"); ax.set_xlim(0, 100)
    ax.set_title("Hold-up time for a 3 W load, supercapacitor bank on the 5 V rail", loc="left", fontsize=11)
    ax.legend(title="Bank capacitance", frameon=False)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "holdup.png"), dpi=200); plt.close(fig)

    rep.append("\nCHARGING a 10 F bank from empty (no load)\ncase | time to 4.75 V (s) | buck restarts")
    fig, ax = plt.subplots(figsize=(8, 4.2))
    # cases where the panel cannot carry the charge current collapse and restart; those are run for 3 s only
    cases = [("full sun, direct on buck", 1.0, None, 120, "5m"), ("10 % sun, direct on buck", 0.1, None, 3, "50u"),
             ("10 % sun, 0.5 A limited charger", 0.1, 0.5, 120, "5m"), ("5 % sun, 0.5 A limited charger", 0.05, 0.5, 3, "50u")]
    for (label, g, lim, ts, ms), col in zip(cases, C):
        d = charge(g, limited=lim, tstop=ts, maxstep=ms)
        rep.append(f"   [{label}] after {ts} s: supercap at {d['vsc'][-1]:.2f} V, mean panel voltage {d['vin'].mean():.1f} V")
        done = np.argmax(d["vsc"] >= 4.75)
        td = d["time"][done] if done else float("nan")
        n = int((np.diff((d["ven"] > 0.5).astype(int)) > 0).sum())
        rep.append(f"{label} | {td:.0f} | {n}")
        ax.plot(d["time"], d["vsc"], color=col, label=label)
    ax.set_xlabel("Time (s)"); ax.set_ylabel("Supercapacitor voltage (V)")
    ax.set_title("Charging a 10 F bank from empty", loc="left", fontsize=11); ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "charge.png"), dpi=200); plt.close(fig)

    txt = "\n".join(rep)
    open(os.path.join(OUT, "results.txt"), "w").write(txt + "\n")
    print(txt)
