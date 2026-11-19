# Power simulation (first pass)

System-level ngspice model of the solar input, 5 V buck and supercapacitor hold-up.
Run `python3 power_sim.py` (needs ngspice, numpy, matplotlib). Results land in `out/`.

The buck is an averaged behavioural model (regulation, current limit, dropout, enable
hysteresis, soft start). It does not model switching ripple, loop stability or the
LMR51430 hiccup protection. Those need the vendor model once the schematic exists.

Every value marked ASSUMED at the top of `power_sim.py` is a placeholder: the panel
(generic 50 W, 36 cells, Voc 22 V, Isc 3 A), 3 W load, 90 % buck efficiency, and the
3.7 V load cut-off on the 5 V rail.
