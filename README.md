# Open perfusion rig

Math, a text protocol, Arduino-style firmware, and a parametric plunger carriage for a **syringe pusher** used on in-vitro perfusion (organoids, tissue chips).

The printed part pushes a plunger. Medium stays in a sterile disposable syringe and purchased tubing. A 0.22 µm filter belongs in that line if the fluid is going into a culture. PLA is not a sterile fluid path, and ethanol wiped on a print is not sterilization.

## Non-goals

- Not an infusion pump. Not for animals or people. The firmware refuses flows above 2000 µL/min.
- Not a biosafety cabinet, incubator, or autoclave.
- Not a measured calibration of your syringe. Catalog inner diameters are a starting guess. `diameter_from_water_mass` turns a gravimetric extrusion (mg of water, mm of travel) into a diameter because 1 mg of water is 1 µL.

## What is tested

Cylinder volume, inversion of that calibration, and that a script's integrated volume matches the step count the host simulator computes from the same diameter, pitch, and microstepping. The `.ino` implements that command set (`DIA`, `PITCH`, `MICRO`, `FLOW`, `RUN`, `STOP`, `STATUS`). The simulator is the reference. Flash the sketch only after you have read the pin comments and you are using a commercial enclosed 12 V supply.

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
