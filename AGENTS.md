# Agent instructions — open-perfusion-rig

Work only in this repository. This is syringe-pusher math, a text command set,
and an untested Arduino-style sketch. Medium stays in a disposable syringe.
PLA is not a sterile fluid path. Not an infusion pump. Firmware refuses flows
above 2000 µL/min.

## Do not

- Stream `encode()` output at the sketch. It does not queue a script; a later RUN/STOP can cancel motion. A transport must wait for `OK DONE`.
- Claim a physical calibration. Catalog diameter is a guess. Gravimetric analysis belongs in `perfusion-calibration-lab`.
- Raise the flow ceiling or aim this at animals or people.
- Pretend the simulator includes backlash, pressure, occlusion, motor dynamics, or missed steps. Pulse quantization *is* now modeled (`--quantization`): uint32 interval truncation, whole steps, and the millisecond run clock, taken from the sketch's arithmetic. Nothing else is.

## First commands

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
PYTHONPATH=src python3 -m perfusion.cli --diameter-mm 14.5 --pitch-mm 8 --microsteps 16 --flow 50 --minutes 30
```

## Improve, in this order

1. Keep host validation stricter than the sketch, and keep a test that integrated volume matches step count.
2. Allowed: document the serial turn-taking state machine in comments or a short doc. Do not flash hardware from this agent.
3. If you change `diameter_from_water_mass`, keep the density argument explicit. Default 1 mg/µL is an approximation.
4. Do not commit STL dumps or claim a print was measured unless you add the measurement file and its uncertainty.

## Done when

`make test` passes and the README still says the sketch was not hardware-tested in the last edit unless you actually did that and wrote how.
