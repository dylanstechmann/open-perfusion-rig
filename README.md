# Open perfusion rig

Math, a text protocol, Arduino-style firmware, and a parametric plunger carriage for a **syringe pusher** used on in-vitro perfusion (organoids, tissue chips).

The printed part pushes a plunger. Medium stays in a sterile disposable syringe and purchased tubing. A 0.22 µm filter belongs in that line if the fluid is going into a culture. PLA is not a sterile fluid path, and ethanol wiped on a print is not sterilization.

## Non-goals

- Not an infusion pump. Not for animals or people. The firmware refuses flows above 2000 µL/min.
- Not a biosafety cabinet, incubator, or autoclave.
- Not a measured calibration of your syringe. Catalog inner diameters are a starting guess. `diameter_from_water_mass` turns a gravimetric extrusion (mg of water, mm of travel) into a diameter using an approximate default density of 1 mg/µL or a supplied measured density.

## What is tested

Cylinder volume, inversion of that calibration, and that a script's integrated volume matches the step count the host simulator computes from the same diameter, pitch, and microstepping. The `.ino` implements that command set (`DIA`, `PITCH`, `MICRO`, `FLOW`, `RUN`, `STOP`, `STATUS`). The host simulator models sequential, completed commands; see the firmware transport limitation below. Flash the sketch only after you have read the pin comments and you are using a commercial enclosed 12 V supply.

## Run

```bash
make test
PYTHONPATH=src python3 -m perfusion.cli \
  --diameter-mm 14.5 --pitch-mm 8 --microsteps 16 \
  --flow 50 --minutes 30
```

Python 3.10+. The host tool has no hardware dependency.

`hardware/syringe_carriage.scad` is parametric. Measure the barrel and the leadscrew nut before printing. OpenSCAD is not required to run the tests.

## A small bill of materials

NEMA 17, T8 leadscrew and nut, a Pololu-style stepper driver, an Arduino-class board, a commercial 12 V supply, a disposable syringe, sterile luer tubing, and an in-line 0.22 µm filter when the outlet is a culture. Ballpark US$150–400 in parts, which is the pump, not the lab. A real mammalian setup still needs a Class II cabinet and a CO₂ incubator that this repo does not pretend to replace.

## License

MIT for the code and the OpenSCAD. You still have to follow the syringe, driver, and biosafety rules of wherever the rig actually sits.

## Host validation and measurement (v0.2)

Install with `python -m pip install -e .`. The host rejects NaN/infinity, invalid
command arity, unsupported microsteps, nonpositive runs and runs longer than
86,400 seconds. Encoding also checks values after text rounding. Each simulated
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

Host-side validation is stricter than the current sketch and does not protect
commands sent directly to it. The sketch was not changed or hardware-tested
in this revision. The simulator models ideal signed displacement, not pulse
quantization, backlash, pressure, occlusion, evaporation or delivered volume.
Firmware hardening, board compilation and physical commissioning remain open
work. The code is not a validated hardware controller.
