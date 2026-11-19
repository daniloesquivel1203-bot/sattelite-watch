#!/usr/bin/env python3
"""Receiver supply as redrawn: TPS62065 at 3.35 V, C3 22 uF, then three damped LC rail filters.

Small-signal check in closed form (numpy). The TPS62065 control loop is internal and I have no vendor model here,
so the buck is a GENERIC current-mode loop: integrator-plus-zero compensator sized for a chosen crossover on C3 alone.
The question answered is how much the three filters disturb such a loop, not the part's absolute phase margin.
ASSUMED: capacitor derating (22 uF -> 18 uF, 47 uF -> 23 uF at 3.35 V), ESR 3 mohm, ESL 0.6 nH, soft-start time.
"""
import os, numpy as np
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
f = np.logspace(2, 8, 6001); s = 2j * np.pi * f
cap = lambda c, esr=3e-3, esl=0.6e-9: 1 / (s * c) + esr + s * esl
par = lambda *z: 1 / sum(1 / x for x in z)
LOADS = {"3.3V_RF": 0.156, "3.3V_SYNTH": 0.182, "3.3V_ADC": 0.060}

def rail(i_load, c=18e-6, cd=23e-6, rd=0.5, l=2.2e-6, dcr=0.084):
    zo = par(cap(c), cap(cd) + rd, 3.3 / i_load)       # at the rail
    zin = s * l + dcr + zo                               # seen from the buck output
    return zin, zo / zin                                 # input impedance, transfer buck->rail

def loop(fc, c3=18e-6, with_filters=True, **kw):
    z = [cap(c3)] + ([rail(i, **kw)[0] for i in LOADS.values()] if with_filters else [np.full_like(s, 3.35 / 0.4)])
    zl = par(*z)
    g = 2 * np.pi * fc * c3 * (1 + 2 * np.pi * fc / 5 / s)   # compensator: crossover fc on C3 alone, zero at fc/5
    t = g * zl
    mag = np.abs(t); ph = np.unwrap(np.angle(t))
    cross = np.where(np.diff(np.sign(mag - 1)))[0]
    return [(f[k], 180 + np.degrees(ph[k])) for k in cross], zl

rep = ["RAIL FILTER as drawn (2.2 uH 84 mohm, 22 uF + [47 uF + 0.5 ohm]), by capacitor derating",
       "case | peaking dB | at Hz | attenuation at 3 MHz dB | at 51 MHz dB"]
at = lambda h, x: 20 * np.log10(np.abs(h[np.argmin(np.abs(f - x))]))
for name, kw in (("nominal 22 / 47 uF", dict(c=22e-6, cd=47e-6)), ("derated 18 / 23 uF", {}), ("derated, damper 0.33 ohm", dict(rd=0.33)),
                 ("derated, damper 1 ohm", dict(rd=1.0)), ("derated, two 47 uF in damper (46 uF eff.)", dict(cd=46e-6))):
    h = rail(0.182, **kw)[1]; m = 20 * np.log10(np.abs(h)); k = np.argmax(m)
    rep.append(f"{name} | {m[k]:.1f} | {f[k]:.0f} | {at(h, 3e6):.0f} | {at(h, 51e6):.0f}")
rep.append(f"DC drop: SYNTH {84*0.182:.0f} mV, RF {84*0.156:.0f} mV, ADC {84*0.060:.0f} mV -> rails at about {3.35-0.084*0.182:.3f} / {3.35-0.084*0.156:.3f} / {3.35-0.084*0.060:.3f} V")
rep += ["", "GENERIC BUCK LOOP with and without the three filters (phase margin at each unity-gain crossing)",
        "assumed crossover on C3 alone | without filters | with filters (derated caps)"]
for fc in (50e3, 100e3, 200e3, 300e3):
    a, _ = loop(fc, with_filters=False); b, zl = loop(fc)
    fmt = lambda x: ", ".join(f"{p:.0f} deg at {q/1e3:.0f} kHz" for q, p in x)
    rep.append(f"{fc/1e3:.0f} kHz | {fmt(a)} | {fmt(b)}")
_, zl = loop(100e3); zc = np.abs(cap(18e-6)); zf = np.abs(par(*[rail(i)[0] for i in LOADS.values()]))
k = np.argmin(zf)
rep.append(f"lowest impedance of the three filters seen from the buck: {zf[k]*1e3:.0f} mohm at {f[k]/1e3:.0f} kHz (C3 alone there: {zc[k]*1e3:.0f} mohm)")
ctot = 18e-6 + 3 * (18e-6 + 23e-6)
rep += ["", f"START-UP: total capacitance charged {ctot*1e6:.0f} uF (derated) to 3.35 V, plus 0.4 A load",
        "soft-start time ASSUMED | inductor current needed A"]
for tss in (100e-6, 250e-6, 500e-6, 1e-3):
    rep.append(f"{tss*1e6:.0f} us | {ctot*3.35/tss + 0.4:.2f}")
rep += ["", "SWITCHING HARMONICS in the 50 MHz IF band (44.75 to 55.25 MHz if centred on 50), 3 MHz +/- 10 % oscillator",
        "harmonics of exactly 3.0 MHz in band: " + ", ".join(f"{n}th = {3*n} MHz" for n in range(1, 30) if 44.75 <= 3*n <= 55.25),
        "with +/- 10 % tolerance any of the 14th to 20th harmonics can land in band; there are always 3 or 4 in band"]
open(f"{OUT}/buck_filters.txt", "w").write("\n".join(rep) + "\n"); print("\n".join(rep))
