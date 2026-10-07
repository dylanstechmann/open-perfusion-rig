# Open perfusion rig

This is a personal hobby and learning project, developed with substantial assistance from AI coding tools.

Math, a text protocol, Arduino-style firmware, and a parametric plunger carriage for a **syringe pusher** used on in-vitro perfusion (organoids, tissue chips).

The printed part pushes a plunger. Medium stays in a sterile disposable syringe and purchased tubing. A 0.22 µm filter belongs in that line if the fluid is going into a culture. PLA is not a sterile fluid path, and ethanol wiped on a print is not sterilization.

## Non-goals

- Not an infusion pump. Not for animals or people. The host and firmware reject flows above 2000 µL/min and nonzero flows below 0.01 µL/min, where the firmware disables the motor. These software bounds do not establish delivered-flow accuracy.
- Not a biosafety cabinet, incubator, or autoclave.
- Not a measured calibration of your syringe. Catalog inner diameters are a starting guess. `diameter_from_water_mass` turns a gravimetric extrusion (mg of water, mm of travel) into a diameter using an approximate default density of 1 mg/µL or a supplied measured density.

## Discrete pulse quantization

`--quantization` reports what the sketch's integer scheduling actually delivers,
instead of the continuous integral:

- the exact step interval and the `uint32_t` value the sketch stores, which
  **truncates** rather than rounds, so the realized step rate is never slower
  than requested;
- whole steps only — the final fractional step never fires;
- the run length as whole milliseconds, since the sketch compares `millis()`
  against `(uint32_t)(seconds * 1000)`;
- volume per microstep, the smallest increment the rig can deliver, and the
  resulting within-interval flow pattern.

The two effects pull in opposite directions and their balance depends on flow.
At 50 µL/min for 30 min with a 14.5 mm barrel, 8 mm pitch and 16 microsteps, the
schedule delivers 3,633 steps — 1499.79 µL against the continuous model's 1500
µL, −0.014%. At 10 µL/min one step takes about 2.5 s, so a 60 s run fires only
24 steps and the unfired remainder costs −0.9%. An assumed per-pulse loop
overhead can only reduce delivery, because the sketch can fire late but never
early; at a 2.5 s interval 50 µs of overhead changes nothing, while at
1500 µL/min it removes steps.

This is scheduling arithmetic, not a measured volume. Motor acceleration,
pull-out torque, missed steps, backlash, compliance, pressure, occlusion and
leaks are still not modeled, and no hardware was operated. Gravimetric
measurement belongs in
[perfusion-calibration-lab](https://github.com/dylanstechmann/perfusion-calibration-lab).

## What is tested

Cylinder volume, inversion of that calibration, and that a script's integrated volume matches the step count the host simulator computes from the same diameter, pitch, and microstepping. The `.ino` implements that command set (`DIA`, `PITCH`, `MICRO`, `FLOW`, `RUN`, `STOP`, `STATUS`). The host simulator models sequential, completed commands; see the firmware transport limitation below. Flash the sketch only after you have read the pin comments and you are using a commercial enclosed 12 V supply.

## Run

```bash
make test

# Constant flow profile
PYTHONPATH=src python3 -m perfusion.cli \
  --diameter-mm 14.5 --pitch-mm 8 --microsteps 16 \
  --flow 50 --minutes 30

# Multi-segment ramp -> hold -> ramp profile
PYTHONPATH=src python3 -m perfusion.cli \
  --diameter-mm 14.5 --pitch-mm 8 --microsteps 16 \
  --profile ramp_hold_ramp \
  --flow-low 10 --flow-high 80 \
  --ramp-up-s 30 --hold-s 60 --ramp-down-s 30

# Pulsatile flow simulation profile
PYTHONPATH=src python3 -m perfusion.cli \
  --diameter-mm 14.5 --pitch-mm 8 --microsteps 16 \
  --profile pulsatile \
  --base-flow 10 --peak-flow 120 \
  --cycle-s 2.0 --cycles 30 --duty-cycle 0.4
```

Python 3.10+. The host tool has no hardware dependency. Generated scripts are strictly validated against firmware opcodes and bounds before emission.

`hardware/syringe_carriage.scad` is parametric. Measure the barrel and the leadscrew nut before printing. OpenSCAD is not required to run the tests.

## A small bill of materials

NEMA 17, T8 leadscrew and nut, a Pololu-style stepper driver, an Arduino-class board, a commercial 12 V supply, a disposable syringe, sterile luer tubing, and an in-line 0.22 µm filter when the outlet is a culture. Ballpark US$150–400 in parts, which is the pump, not the lab. A real mammalian setup still needs a Class II cabinet and a CO₂ incubator that this repo does not pretend to replace.

## License

MIT for the code and the OpenSCAD. You still have to follow the syringe, driver, and biosafety rules of wherever the rig actually sits.

## Host validation and measurement (v0.2)

Install with `python -m pip install -e .`. The host rejects NaN/infinity, invalid
command arity, unsupported microsteps, runs below the one-millisecond clock
resolution and runs longer than 86,400 seconds. Encoding also checks values after text rounding. Each simulated
RUN clears the flow on completion, matching that part of the firmware state.

`diameter_from_water_mass(..., density_mg_ul=...)` supports a supplied density.
The default 1 mg/µL is an approximation, not an exact water property. For
balance traces and independent repeat runs, use
[perfusion-calibration-lab](https://github.com/dylanstechmann/perfusion-calibration-lab).
It reports measured flow, repeat variability and drift without sending commands.

### Firmware transport limitation

The sketch is asynchronous and **does not queue a script**. Do not stream
`encode()` output directly into its serial port: a later FLOW, RUN or STOP can
replace or cancel an active run. A future transport must wait for `OK DONE`
after each RUN before proceeding. The current Python CLI only prints/simulates;
it is not that transport.

The [current serial state and replies](docs/SERIAL_TURN_TAKING.md) are documented
for review. Configuration commands have no success acknowledgement, and
`OK DONE` reports elapsed run time rather than measured delivery.

Host and sketch validation now reject malformed/non-finite
arguments, invalid arity, fractional microstep values, overlong runs, and
requested step intervals shorter than its four-microsecond STEP pulse or longer
than the 32-bit timer range. The host simulator applies the same interval
bounds. A native `g++` harness compiles the actual `.ino` against fake serial,
clock and pin functions to exercise parser, turn-taking, completion, pulse
phase after idle, and 32-bit millisecond/microsecond rollover behavior;
it is not an Arduino board build or a hardware test.

The sketch has not been hardware-tested. No board toolchain or physical
delivery trace was available for this revision.
The simulator models ideal signed displacement, not pulse quantization,
backlash, pressure, occlusion, evaporation or delivered volume. Board-specific
timing/geometry validation and physical commissioning remain open. The code is
not a validated hardware controller.
