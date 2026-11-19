#!/usr/bin/env python3
"""Switcher-only receiver rails: attenuation of a per-rail LC filter and the resulting LO spur estimate.

ASSUMED: 3.3 V forced-PWM buck at 2.2 MHz with 10 mV pk-pk output ripple; filter 2.2 uH (0.1 ohm DCR) into
22 uF ceramic (3 mohm ESR, 0.6 nH ESL) plus a damping branch of 47 uF in series with 0.5 ohm; ADF4351 VCO
supply pushing 1 MHz/V (recalled from memory, to be checked); LDO PSRR figures are rough LP5907-class values.
"""
import os, subprocess, math, numpy as np
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
FSW, RIPPLE_PP, PUSH = 2.2e6, 10e-3, 1e6

def filt(load_ma):
    n = f"""* rail LC filter
V1 in 0 dc 3.3 ac 1
L1 in a 2.2u
Rdcr a out 0.1
C1 out c1 22u
Rc1 c1 c1l 3m
Lc1 c1l 0 0.6n
Cd out d 47u
Rd d 0 0.5
Rl out 0 {3.3/(load_ma/1000)}
.control
set wr_singlescale
set wr_vecnames
ac dec 50 100 100meg
wrdata {OUT}/f.txt vdb(out)
.endc
.end
"""
    open(f"{OUT}/rail_filter.cir", "w").write(n)
    subprocess.run(["ngspice", "-b", f"{OUT}/rail_filter.cir"], capture_output=True)
    d = np.genfromtxt(f"{OUT}/f.txt", names=True); os.remove(f"{OUT}/f.txt")
    return d[d.dtype.names[0]], d[d.dtype.names[1]]

def spur_dbc(ripple_pk, fm):   # narrow-band FM sideband from supply pushing
    return 20 * math.log10(PUSH * ripple_pk / fm / 2)

if __name__ == "__main__":
    f, db = filt(150)
    at = lambda x: float(np.interp(math.log10(x), np.log10(f), db))
    rep = ["LC filter per rail (2.2 uH + 22 uF, damped), 150 mA load",
           "frequency | attenuation dB",
           *[f"{x:g} Hz | {at(x):.1f}" for x in (1e3, 1e4, 2e4, 1e5, 1e6, FSW, 2*FSW, 50e6)],
           f"peaking: {db.max():.1f} dB at {f[np.argmax(db)]:.0f} Hz",
           f"DC drop at 180 mA: {0.1*0.18*1000:.0f} mV",
           "",
           f"LO spur at the switching frequency ({FSW/1e6:g} MHz offset), {RIPPLE_PP*1e3:g} mV pk-pk ripple, pushing {PUSH/1e6:g} MHz/V",
           "supply path to the synthesizer | ripple at the pin (uV pk) | spur dBc"]
    pk = RIPPLE_PP / 2
    for name, a in (("buck direct, no filter", 0.0), ("buck + LDO (about 40 dB PSRR at 2 MHz, ASSUMED)", -40.0),
                    ("buck + LC filter", at(FSW)), ("buck + LC filter + LDO", at(FSW) - 40.0)):
        r = pk * 10 ** (a / 20)
        rep.append(f"{name} | {r*1e6:.2f} | {spur_dbc(r, FSW):.0f}")
    i = 309.0
    rep += ["", "Power drawn from 5V_MAIN by the receiver (309 mA typical at 3.3 V, 90 % buck efficiency ASSUMED)",
            f"three LDOs from 5 V (as drawn): {5*i/1000:.2f} W",
            f"3.6 V buck then three LDOs: {3.6*i/1000/0.9:.2f} W",
            f"3.3 V buck with LC filters only: {3.3*i/1000/0.9:.2f} W"]
    open(f"{OUT}/rail_filter.txt", "w").write("\n".join(rep) + "\n"); print("\n".join(rep))
