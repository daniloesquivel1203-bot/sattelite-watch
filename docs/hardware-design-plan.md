# Backyard Satellite Tracker: Hardware Design Plan

Nov 10, 2026 · @Danilo

**Status:** approved by Danilo on 2026-11-11 as the version 1 design baseline.

## Summary

The device is a flat, roughly 22 cm square receive-only panel that listens to Iridium satellites at 1.62 GHz with a four-element phased array, measures the direction each signal arrives from, and follows a satellite across the sky until the next one takes over. A small GNSS module adds a live view of every GPS, Galileo, GLONASS and BeiDou satellite overhead.

- **Band:** L-band, 1616 to 1626.5 MHz for Iridium and 1559 to 1610 MHz for GNSS. Receive-only, so no license is needed.
- **Antenna:** 2x2 patch array with digital beamforming. No motor in version 1.
- **SoC:** Octavo OSD32MP157C, an STM32MP157 with memory and power management in one package, running Linux.
- **Connectivity:** 2.4 GHz Wi-Fi module, USB-C device port, USB-A host port.
- **Power:** about 3 W, fed directly from a 50 W solar panel. Version 1 runs in daylight only, and the battery is deferred.
- **Heat:** leaving the battery out removes the part least able to take 120 F. The electronics are industrial grade and shaded from direct sun.
- **Cost:** about 520 USD for the first unit without a battery, close to the 500 USD target.

Part numbers here are candidates. Each one gets checked against its datasheet and current stock before schematic work starts.

## Requirements and decisions

These come from the original request and the interview on 2026-11-10.

| Topic | Decision |
| --- | --- |
| Location | Backyard in Phoenix, Arizona, residential, no HOA |
| What "track" means | Receive real signals from satellites as they pass and follow one across the sky, then hand over to the next. Orbit predictions are used only as a cross-check. |
| Licensing | Receive-only. No ham license today, one is planned later. Receiving needs no license on any band. |
| Band | L-band, chosen so the antenna stays small and many satellites are visible |
| Antenna | Flat phased-array panel. A motor is optional, not a pole antenna. |
| Build style | Custom PCB, with off-the-shelf parts where they save risk |
| Network | 2.4 GHz Wi-Fi, mounted near an access point |
| USB-C | Phone or computer plugs in here. The device appears as a network adapter and serves the same web page as Wi-Fi. Also a second power input. |
| USB-A | Second way to connect when no USB-C cable is at hand (see the USB section for how this works) |
| Power | Solar only for version 1, running in daylight. The battery for overnight use is deferred because of the heat. |
| Environment | Outdoors all day, 30 F to 120 F ambient (-1 C to 49 C) |
| Size | As small as the band allows |
| Budget | 300 to 500 USD in parts |

### Out of scope: transmitting to find silent satellites

Finding a satellite that is not transmitting means building a radar, and that is not practical for this device. The echo from a satellite 500 km or more away falls off with the fourth power of distance. Real space-surveillance radars use megawatts of power and antennas tens of meters across. A ham license does not make that achievable.

Silent satellites can still be covered two ways. Orbit predictions already list them, and a later add-on camera could photograph sunlit satellites at dusk and dawn. A ham license later would allow talking through amateur satellites on 145 and 435 MHz, which is a separate radio and antenna.

## Signals and frequency bands

Iridium is the main target because it matches the "follow one, then switch" idea exactly. The constellation has 66 active satellites in low orbit, at least one is always in view, each pass lasts roughly 9 minutes, and their signals are strong enough to see above the noise with a patch antenna.

| Signal | Frequency | What the device gets from it | Antenna |
| --- | --- | --- | --- |
| Iridium | 1616 to 1626.5 MHz | Bursts from each satellite in view. The array measures arrival direction, and the broadcast frames identify the satellite. | 2x2 patch array |
| GNSS (GPS, Galileo, GLONASS, BeiDou) | 1559 to 1610 MHz | Azimuth, elevation and signal strength for 30 or more satellites at once, plus exact time and position | One 25 mm patch on a GNSS module |
| Orbit data (not a radio signal) | Downloaded over Wi-Fi | Predicted positions of every catalogued satellite, used to check the measured directions | None |

The [gr-iridium project](https://github.com/muccc/gr-iridium) documents the band as 1.618 to 1.6265 GHz and shows that low-cost receivers can decode it.

L-band keeps the hardware small. The wavelength at 1621 MHz is 18.5 cm, so array elements sit 9.3 cm apart and four of them fit on a panel about 20 cm square. The same array at 137 MHz would be over 2 m across.

Starlink is outside this band at 10.7 to 12.7 GHz. It is covered by an optional add-on input described in the antenna section.

Both bands are receive-only here. Listening needs no license or training. The only transmitter in the device is the Wi-Fi module, which is pre-certified.

Iridium traffic is partly unencrypted. This design uses only the broadcast and signalling frames needed to identify and locate satellites, and does not store or decode user traffic.

## System architecture

_Block diagram: see the design doc at https://claude.ai/artifact/LfRefnTEVax74mSug3Riau_

The top row is the signal path, the middle row is everything else that talks to the SoC, and the bottom row is power. The four receive channels share one local oscillator and one sample clock, which is what lets the software compare phase between antennas and work out direction.

Physically this is two pieces joined by one cable: the antenna and electronics panel facing the sky, and the tilted solar panel.

## Antenna and RF front end

The antenna is a 2x2 array of right-hand circular patches on a 9.3 cm grid, steered in software instead of by a motor. All four antennas are digitized at once, so the device sees the whole sky continuously and can form a beam on any satellite after the fact.

### What a 2x2 array can and cannot do

- It adds about 6 dB of signal over a single patch.
- Its beam is roughly 50 to 60 degrees wide, so it measures direction to within a few degrees on strong bursts but does not sharply separate two satellites close together.
- It works well from straight overhead down to about 30 degrees above the horizon. Below that the flat panel loses gain.
- A 4x4 array (38 cm square, 16 channels) would narrow the beam to about 25 degrees. The receiver is laid out as a four-channel tile so this upgrade repeats the same circuit.

### Motor

Version 1 has no motor. Digital beamforming already follows satellites electronically, and a motor adds moving parts, dust seals and power draw in a harsh climate. If low-elevation coverage turns out to matter, a single-axis tilt mount can be added later without changing the electronics.

### Receive chain, per antenna

1. Ceramic patch antenna, 25 mm, tuned for 1621 MHz.
2. Band filter and low-noise amplifier placed right at the patch.
3. Mixer that shifts the signal down to about 10 MHz.
4. Amplifier and anti-alias filter.
5. One channel of an analog-to-digital converter sampling at 20 to 40 MHz.

All four mixers are driven by one synthesizer and all four converters by one clock, both derived from a temperature-compensated oscillator. A small FPGA (Lattice iCE40UP5K, with ECP5 as the fallback if it runs out of logic) filters each channel down to the Iridium band and passes the samples to the SoC.

### Why not a single-chip receiver

The obvious part, the MAX2771 GNSS receiver chip, cannot reach Iridium. Its [datasheet](https://www.analog.com/MAX2771/datasheet) limits the upper tuning range to 1610 MHz. A shared-synthesizer design also has a real advantage: the four channels are phase-locked by construction, with nothing to re-align at each power-up.

### Calibration

Cable and filter differences between channels are measured using the satellites themselves. GNSS and Iridium satellites have known positions, so the software solves for the per-channel phase offsets and tracks them as temperature changes.

### GNSS

GNSS uses an off-the-shelf multi-constellation module such as the u-blox MAX-M10S with its own patch. It reports each satellite's azimuth, elevation and signal strength directly and supplies the precise time used to stamp every measurement.

### Optional Starlink input

Starlink is added as an optional fifth input, because the phased array cannot hear it. Starlink satellites transmit down at 10.7 to 12.7 GHz, far above the array's 1.6 GHz band.

- A satellite TV receiver head (LNB, about 15 USD) mounts beside the panel facing up and converts the 11 GHz signals down to 1 to 2 GHz.
- Starlink beacon tones near 11.325 GHz come out of a standard LNB at about 1575 MHz, inside the range the receiver already tunes. This figure is from memory and gets confirmed in phase 0.
- An RF switch lets one of the four receive channels take the LNB instead of its patch. That channel's band filter is bypassed in this mode.
- A bias circuit sends 12 V up the coax to power the LNB, and switches it off when not in use. The LNB draws about 1 W, so it runs on demand and not continuously.
- The result is detection of each Starlink pass and its Doppler shift, which is enough to match it to a specific satellite using orbit data. It does not give direction finding, since one LNB is a single antenna.

## SoC and digital interfaces

The SoC is the Octavo OSD32MP157C-512M-IAA. It packages an ST STM32MP157C (dual Cortex-A7 at 650 MHz plus a Cortex-M4), 512 MB of memory, and the power-management chip in one industrial-temperature BGA. It is sold through normal distributors and has mainline Linux support.

It was chosen because it meets every interface on the list with built-in hardware and removes the hardest part of a first custom Linux board, which is routing memory.

| Need | How the SoC meets it |
| --- | --- |
| USB-C device port | Built-in high-speed USB OTG controller and PHY |
| USB-A host port | Built-in high-speed USB host controller and PHY |
| 2.4 GHz Wi-Fi | SDIO port to a Wi-Fi module |
| Sample data from the FPGA | Parallel camera interface or SPI |
| GNSS module | UART plus a timing-pulse input |
| Storage | microSD or eMMC on a second SD/MMC port |
| Heat | Industrial grade, rated -40 to 85 C ambient |

Approximate price is 50 to 60 USD in single units, from memory and not yet quoted.

### Final selection at build time

The OSD32MP157C was out of stock when checked on 2026-11-11, so it is the reference choice and not a commitment. The final SoC is picked when the build starts, from whatever is in stock and the assembler can place. Any candidate must have:

- Two high-speed USB ports with built-in PHYs, one device-capable and one host.
- An SDIO port for Wi-Fi and a second SD/MMC port for storage.
- A fast input for FPGA sample data, either a parallel interface or SPI.
- Industrial temperature rating, -40 to 85 C.
- Memory in the package, or a simple enough memory layout for a 6-layer board.

Shortlist in order: other OSD32MP15x variants, the Microchip SAMA5D27 system-in-package, then an STM32H7 microcontroller without Linux if neither is available.

### Alternatives considered

- **ESP32-S3:** has Wi-Fi built in, but it is too slow for four-channel signal processing and its USB is full-speed only.
- **Raspberry Pi Compute Module:** it is a module, not an SoC, and draws more power.
- **AMD Zynq-7010:** combines the processor and FPGA in one chip and is the natural upgrade for a 16-channel array, but it needs external memory routing and costs more.

### Wi-Fi

Wi-Fi is a pre-certified 2.4 GHz module on SDIO with a connector for an external antenna, so the antenna can sit outside the enclosure and point at the access point. Two candidates need a temperature-rating check: the Murata Type 1DX used on ST's own development kit, and an Espressif ESP32-C6 module running as a Wi-Fi adapter.

### USB-C

The USB-C port is a device port. A phone or computer that plugs in sees a network adapter and opens the same web page that Wi-Fi serves, at a fixed address. The same port accepts 5 V as a second power input.

### USB-A

A USB-A socket is a host port under the USB standard, so a computer cannot plug into it with a normal cable. The "no USB-C on hand" case is covered two ways:

- **Computer with only USB-A ports:** use a USB-C to USB-A cable into the device's USB-C port. This works the same as C to C.
- **Phone with its normal charging cable:** plug it into the device's USB-A port and turn on USB tethering. The device and phone then share a network link and the phone can open the web page.

The USB-A port also accepts a flash drive for exporting logs or a camera for the later optical add-on. Its 5 V supply is current-limited and switched off when nothing is attached.

## Power

Version 1 runs directly from a 50 W solar panel with no battery, so it works in daylight and is off at night. The load is estimated at 3 W with margin, to be confirmed by measuring the prototype.

### Load estimate

| Block | Average power (W) |
| --- | --- |
| SoC running Linux | 0.9 |
| Four receive channels (amplifiers, mixers, converters) | 0.5 |
| Synthesizer and oscillator | 0.3 |
| Wi-Fi | 0.15 |
| FPGA and GNSS module | 0.1 |
| Regulator losses (about 15%) | 0.3 |
| **Total estimate** | **2.3** |
| **Design figure with margin** | **3.0** |

### Running on solar alone

- The device starts shortly after sunrise and stops shortly before sunset. That is roughly 10 hours a day in December and 14 in June.
- A 50 W panel reaches the 3 W the device needs at well under a tenth of full sun, so it keeps running under ordinary cloud.
- A 30 W panel would also work for daylight-only use. 50 W is kept so the panel does not need replacing when a battery is added.
- The panel is about 55 x 50 cm, tilted about 45 degrees facing south.

### Hold-up

A panel alone drops out for a moment whenever a shadow or thick cloud passes, which would reboot the device. A small supercapacitor bank stores about a minute of run time to ride through these dips and to shut down cleanly at dusk.

- Supercapacitors tolerate heat far better than batteries and have no charging temperature limits.
- The storage is read-only in normal use, so even an abrupt power loss does no harm.
- The GNSS module restores the correct time at every start-up.

### Supply

A wide-input regulator rated for 36 V or more converts the panel voltage to 5 V. A cold 12 V class panel can reach about 23 V open-circuit, so this leaves margin. The USB-C port is a second power input, which allows bench work and night-time testing from a USB power bank.

### Battery, deferred

The battery is left for a later version. The board keeps a battery connector, with a temperature sensor pin, and a fully routed charger circuit whose parts are left unfitted. Adding a battery later means soldering on the charger parts, with no new board.

- The earlier sizing still stands for when it returns: a 12.8 V 20 Ah LiFePO4 pack covers 24/7 use plus two days without sun at a 3 W load.
- The candidate charger was the [TI BQ25798](https://www.ti.com/product/BQ25798).
- The open problem is heat. Typical lithium cells must not be charged above about 45 C, and Phoenix shade temperatures exceed that in summer.

## Thermal and enclosure

The electronics can be built to survive Phoenix. The battery was the part needing the most care, and it is deferred. Air temperature of 120 F (49 C) is manageable, but a sealed box in direct sun can reach 65 to 75 C inside, so the design is mostly about keeping sun off things.

### Battery

Version 1 has no battery, so these limits do not apply yet. They are kept here for the later version.

- Typical LiFePO4 cells allow charging from 0 to 45 C and discharging up to 60 C. Some are rated to charge at 55 or 60 C.
- At 120 F ambient a battery is already above 45 C in the shade, so summer charging would be limited to the morning.
- At 30 F (-1 C) charging is also blocked until the sun warms the pack.
- Options to study later are high-temperature LiFePO4 cells, lithium titanate, sodium-ion, and a shaded or partly buried battery box.

### Electronics

- Every part is industrial grade, rated -40 to 85 C. The target is to keep the air inside the panel below 70 C.
- The device makes only about 3 W of its own heat, which adds 5 to 10 C. Sunlight is the bigger load.
- The antenna face must see the sky, so it gets a white, UV-stable ASA or polycarbonate cover that passes radio signals and reflects sunlight.
- The circuit board mounts to an aluminium back plate with fins on the shaded underside. No fans, since they fail in dust.
- Capacitors are ceramic or polymer types rated to 105 C or higher.
- Cold is not a problem for the electronics at 30 F.

### Weather

- Enclosure sealed to IP65 for monsoon rain and dust storms, with a breather vent so pressure changes do not pull moisture in.
- Waterproof USB connectors with caps, on the underside.
- Surge and static protection on every antenna input and on the solar input.
- The board gets a conformal coating.

### Size and mounting

| Piece | Approximate size | Placement |
| --- | --- | --- |
| Antenna and electronics panel | 22 x 22 x 5 cm | Flat, facing straight up, clear view of the sky |
| Solar panel | 55 x 50 cm | Tilted 45 degrees, facing south |

For version 1 the unit sits on a table in the backyard for testing. The antenna panel gets feet that hold it level with an air gap underneath, and the solar panel gets a folding stand at 45 degrees. Mounting holes are included so a pole, wall or roof bracket can be added later. At table height the house and walls will block satellites low on the horizon, which fits the array's useful range of 30 degrees elevation and up.

## Software outline

The SoC runs a minimal Linux build and turns raw samples into a live sky map served as a web page. This section is a sketch, since the request is for hardware, but the hardware has to support it.

1. The FPGA filters the four channels down to the Iridium band and streams them to the SoC.
2. The SoC detects each burst and computes its arrival direction from the phase differences between antennas.
3. Iridium broadcast frames are decoded with the open-source gr-iridium and iridium-toolkit tools to identify which satellite sent them.
4. The GNSS module reports the direction and signal strength of every navigation satellite in view.
5. Orbit data is downloaded from CelesTrak over Wi-Fi once a day, and predicted positions are compared with measured ones. This is the cross-check, and it also drives array calibration.
6. The tracker locks onto one satellite, follows it until it sets or fades, then hands over to the strongest newcomer.
7. A web page shows a polar sky plot with measured and predicted positions, reachable over Wi-Fi or either USB port.

The device also logs solar input voltage, supply current and internal temperatures, which is the data needed to validate the thermal design and to size a battery later.

## Estimated cost

The first unit comes to about 520 USD without a battery, just over the top of the budget. These are rough figures from memory, not quotes, and each line needs pricing before ordering.

| Item | Estimate (USD) |
| --- | --- |
| Circuit boards, fabricated and assembled, 5 pieces (6-layer main board, antenna board) | 150 |
| Receive chain parts: patches, amplifiers, filters, mixers, converters | 90 |
| Enclosure, antenna cover, vent, cable glands, mounts | 60 |
| SoC (OSD32MP157C) | 55 |
| Solar panel, 50 W | 50 |
| FPGA, synthesizer, oscillator, flash | 30 |
| GNSS module and patch | 25 |
| Storage, USB connectors, passives | 25 |
| Regulator, supercapacitors and power parts | 20 |
| Wi-Fi module and antenna | 12 |
| **Total** | **about 520** |

Ways to get under 500 USD:

- Use a 30 W panel, which is enough for daylight-only running. Saves about 20 USD.
- Hand-assemble the simpler boards. Saves 40 to 60 USD.
- Order three boards instead of five.

Adding the battery and charger later costs about 100 USD.

The bench prototype in phase 0 adds about 60 USD and is worth it, because it proves reception before any board is ordered.

The optional Starlink input adds about 25 USD: the LNB, an RF switch, a coax connector and the bias circuit.

## Build phases and risks

The build goes in five phases so that each risky piece is proven before money is spent on the next.

| Phase | What gets built | What it proves |
| --- | --- | --- |
| 0. Bench proof | A low-cost USB software radio, one Iridium patch and a GNSS module, run from a laptop in the yard | Iridium and GNSS are receivable at this site with a patch antenna |
| 1. Receiver board | The four-channel receiver and antenna array as their own board, driven by SoC and FPGA development kits | Phase-locked channels, direction finding, real power draw |
| 2. Main board | The custom board with the SoC, FPGA, Wi-Fi and both USB ports | Linux boots, all interfaces work |
| 3. Power and enclosure | Power supply board, sealed panel, sun shielding | Runs for a week outdoors without attention, with temperatures logged |
| 4. Summer soak | The complete unit outside through June to August | Electronics stay within limits at 120 F |

### Design tools

Danilo is a hardware engineer and will do schematic capture and layout review. The tools on hand map onto the work like this:

- **KiCad:** schematics and board layout for all boards.
- **Ansys HFSS:** the patch elements, coupling between the four patches, the ground plane size, and the effect of the plastic cover on tuning and pattern.
- **Keysight ADS:** the receive chain from patch to converter, covering amplifier matching, filter response, gain and noise budget, and the split of one synthesizer to four mixers.

For bench measurement, a low-cost vector network analyzer covers patch tuning and filter checks. It must reach at least 2 GHz. The original NanoVNA models stop near 1.5 GHz, so a NanoVNA V2 or LiteVNA class unit is needed, a point to confirm against the specific model before buying. The software radio from phase 0 serves as a basic spectrum viewer.

### Main risks

- **RF design difficulty.** A four-channel phase-matched L-band receiver is the hardest part of the project. Phase 1 isolates it on its own board so mistakes are cheap to fix.
- **No overnight operation.** Without a battery the device is off at night and in very heavy cloud. The battery connector and charger space stay on the board for later.
- **Processing load.** The dual Cortex-A7 may be slow for full Iridium decoding. The FPGA can take on more of the work, or decoding can be limited to the broadcast channels.
- **Solar input voltage.** A cold panel can reach about 23 V open-circuit. The input regulator is rated for 36 V or more.
- **Part availability and assembly.** Every candidate part gets a stock and lifecycle check before schematic capture. The assembly house is chosen first, and each part is checked against what it can source and place, including the SoC's BGA package, the fine-pitch RF parts and X-ray inspection. Parts the assembler cannot supply are bought separately and consigned to them.
- **Cost.** The estimate is already at the top of the budget, and board respins would add to it.

## Review questions, all answered

- [x] Is Iridium as the main target, with GNSS alongside, the right reading of "GPS might be the best one"? GNSS alone would be far simpler but would not need a phased array.
- [x] Is about 600 USD acceptable, or should the design be trimmed to stay under 500 USD?
- [x] What is your PCB experience (BGA parts, 6-layer boards, RF layout) and which design tool do you use? This decides how much to split across boards.
- [x] Do you have access to RF test gear such as a network analyzer or spectrum analyzer?
- [x] Are you happy with no motor in version 1?
- [x] Where exactly will it mount (ground stand, wall, roof), and are there trees or walls blocking part of the sky?
- [x] Is daylight-only running acceptable for version 1, with USB-C power for any night-time testing?

## Next steps

1. **Phase 0 shopping.** Buy a low-cost USB software radio, an Iridium patch antenna, a GNSS module breakout, a satellite TV LNB for the Starlink check, and a network analyzer that reaches at least 2 GHz. Roughly 150 to 200 USD in total, most of it reusable test gear.
2. **Phase 0 test.** Receive Iridium and GNSS from the backyard table with a laptop, and confirm the Starlink beacon frequency through the LNB.
3. **Choose the assembly house** and get its parts library and design rules, since that drives part selection.
4. **Lock the parts list.** Check stock and datasheets for every candidate part, pick the SoC from the shortlist, and price the bill of materials.
5. **Simulate the antenna.** Model the 2x2 patch array and cover in HFSS, and the receive chain in ADS.
6. **Start the phase 1 receiver board** schematic in KiCad.

## Sources

- [gr-iridium](https://github.com/muccc/gr-iridium): Iridium band limits and receiver requirements.
- [MAX2771 datasheet](https://www.analog.com/MAX2771/datasheet): tuning range that rules it out for Iridium.
- [TI BQ25798 product page](https://www.ti.com/product/BQ25798): charger input range, cell count, solar and dual-input features.

Figures not linked to a source, including prices, solar hours, battery temperature limits and power estimates, are approximate and from general knowledge.
