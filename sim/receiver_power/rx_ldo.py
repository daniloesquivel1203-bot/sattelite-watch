#!/usr/bin/env python3
"""Receiver board power sheet check: three LP5907-3.3 LDOs from 5V_MAIN.

Behavioural LDO model (not the TI model). ASSUMED values are marked; load currents are
datasheet typicals recalled from memory and need checking against the datasheets.
"""
import os, subprocess, numpy as np
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# rail: (typical mA, high-side mA) -- ASSUMED from datasheet typicals
RAILS = {
    "3.3V_RF":    (4*4.1 + 4*15 + 4*10, 4*4.1 + 4*15 + 4*20),   # 4x MAX2659, 4x MAX2682, 4x IF amp (10-20 mA guess)
    "3.3V_SYNTH": (27 + 70 + 2*24 + 4, 32 + 80 + 2*32 + 6),      # ADF4351 core + VCO + two RF outputs, TCXO
    "3.3V_ADC":   (2*22, 2*30),                                  # 2x MAX1193 incl. output drivers
}
THETA_JA = 190.0     # C/W, SOT-23-5 on a JEDEC board, ASSUMED (real board copper may reach about 150)
T_AMB = 70.0
ILIM, RDO, TSS = 0.45, 0.5, 80e-6   # LP5907 current limit, dropout resistance (120 mV at 250 mA), start time: ASSUMED

def thermal():
    rows = ["rail | load mA (typ / high) | LDO loss mW at 5.0 V in | junction C at 70 C ambient | at 3.7 V in"]
    for r, (typ, hi) in RAILS.items():
        p = [(5.0 - 3.3) * i for i in (typ, hi)]
        tj = [T_AMB + THETA_JA * x / 1000 for x in p]
        tj37 = T_AMB + THETA_JA * 0.4 * hi / 1000
        rows.append(f"{r} | {typ:.0f} / {hi:.0f} | {p[0]:.0f} / {p[1]:.0f} | {tj[0]:.0f} / {tj[1]:.0f} | {tj37:.0f}")
    tot = sum(v[0] for v in RAILS.values())
    rows.append(f"total typ {tot:.0f} mA: {5*tot/1000:.2f} W drawn from 5V_MAIN, of which {(1.7*tot)/1000:.2f} W is LDO heat")
    return rows

def startup(vin, bulk, level="hi"):
    n = f"* rx ldo startup vin={vin} bulk={bulk}\nVs src 0 {vin}\nRc src a 0.1\nLc a in 100n\nCin in 0 {3e-6 + bulk} ic={vin}\nRcin in 0 1meg\n"
    n += f"Ven en 0 PWL(0 0 100u 0 101u 1)\nRss en ss 1k\nCss ss 0 {TSS/3/1e3} ic=0\n"
    for k, (r, (typ, hi)) in enumerate(RAILS.items()):
        i = (hi if level == "hi" else typ) / 1000
        n += (f"B{k} in o{k} I = V(en) > 0.5 ? min(min({ILIM}, max(0, 200*(3.3*V(ss) - V(o{k})))), max(0, (V(in) - V(o{k}))/{RDO})) : 0\n"
              f"Co{k} o{k} 0 4.7u ic=0\nRl{k} o{k} 0 {3.3/i}\n")
    n += (".options method=gear\n.control\nset wr_singlescale\nset wr_vecnames\ntran 0.2u 600u 0 0.2u uic\n"
          f"wrdata {OUT}/t.txt v(in) v(o0) v(o1) v(o2) vs#branch\n.endc\n.end\n")
    open(f"{OUT}/startup_vin{vin}_bulk{bulk*1e6:g}u.cir", "w").write(n)
    subprocess.run(["ngspice", "-b", f"{OUT}/startup_vin{vin}_bulk{bulk*1e6:g}u.cir"], capture_output=True)
    d = np.genfromtxt(f"{OUT}/t.txt", names=True, comments=None); os.remove(f"{OUT}/t.txt")
    return d

if __name__ == "__main__":
    rep = thermal()
    rep.append("\nSTART-UP, RX_PWR_EN rises at 100 us, all rails at high-side load, 4.7 uF per rail, 0.1 ohm + 100 nH feed")
    rep.append("5V_MAIN | bulk on receiver input | lowest input V | peak input current A | rails final V (RF/SYNTH/ADC) | time to 3.2 V us")
    keep = None
    for vin in (5.0, 3.7):
        for bulk in (0.0, 10e-6, 22e-6):
            d = startup(vin, bulk)
            t = d["time"]; done = max(t[np.argmax(d[k] > 3.2)] for k in ("vo0", "vo1", "vo2")) - 100e-6
            rep.append(f"{vin} | {bulk*1e6:g} uF | {d['vin'].min():.2f} | {abs(d[[k for k in d.dtype.names if "branch" in k][0]]).max():.2f} | "
                       f"{d['vo0'][-1]:.2f}/{d['vo1'][-1]:.2f}/{d['vo2'][-1]:.2f} | {done*1e6:.0f}")
            if vin == 5.0 and bulk == 0.0: keep = d
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
    plt.rcParams.update({"figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "axes.spines.top": False,
                         "axes.spines.right": False, "axes.grid": True, "grid.color": "#e8e7e2", "lines.linewidth": 2})
    fig, ax = plt.subplots(figsize=(8, 4.2)); t = keep["time"] * 1e6
    for k, lab, c in (("vin", "5V_MAIN at the receiver", C[0]), ("vo0", "3.3V_RF", C[1]), ("vo1", "3.3V_SYNTH", C[2]), ("vo2", "3.3V_ADC", C[3])):
        ax.plot(t, keep[k], color=c, label=lab)
    ax.set_xlabel("Time (us)"); ax.set_ylabel("Voltage (V)"); ax.legend(frameon=False)
    ax.set_title("Receiver rails starting together, no bulk capacitor on the input", loc="left", fontsize=11)
    fig.tight_layout(); fig.savefig(f"{OUT}/startup.png", dpi=200)
    open(f"{OUT}/results.txt", "w").write("\n".join(rep) + "\n"); print("\n".join(rep))
