"""Displacement math for a leadscrew syringe pusher.

The fluid path is the sterile syringe and purchased tubing. Printed parts
push the plunger. They do not touch the medium.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

FULL_STEPS = 200
MAX_FLOW_UL_PER_MIN = 2000.0
MAX_RUN_SECONDS = 86400.0


class PumpError(ValueError):
    pass


def volume_ul_per_revolution(diameter_mm: float, pitch_mm: float) -> float:
    if not all(math.isfinite(v) and v > 0 for v in (diameter_mm, pitch_mm)):
        raise PumpError("diameter and pitch must be finite and positive")
    if not 1.0 <= diameter_mm <= 40.0:
        raise PumpError("diameter looks like the wrong unit or the wrong syringe")
    radius = diameter_mm / 2.0
    return math.pi * radius * radius * pitch_mm


def diameter_from_water_mass(mass_mg: float, travel_mm: float, *, density_mg_ul: float = 1.0) -> float:
    """Infer effective diameter. Default density 1 mg/µL is an approximation."""
    if not all(math.isfinite(v) and v > 0 for v in (mass_mg, travel_mm, density_mg_ul)):
        raise PumpError("calibration inputs must be finite and positive")
    radius = math.sqrt((mass_mg / density_mg_ul) / (math.pi * travel_mm))
    return 2.0 * radius


def steps_for_volume(volume_ul: float, diameter_mm: float, pitch_mm: float, microsteps: int = 16) -> float:
    if not math.isfinite(volume_ul):
        raise PumpError("volume must be finite")
    if isinstance(microsteps, bool) or microsteps not in {1, 2, 4, 8, 16}:
        raise PumpError("microsteps must be 1, 2, 4, 8, or 16")
    per_rev = volume_ul_per_revolution(diameter_mm, pitch_mm)
    return volume_ul / per_rev * FULL_STEPS * microsteps


@dataclass
class Segment:
    duration_s: float
    flow_ul_per_min: float

    def __post_init__(self):
        if not math.isfinite(self.duration_s) or not 0 < self.duration_s <= MAX_RUN_SECONDS:
            raise PumpError("duration must be finite, positive and at most 86400 seconds")
        if not math.isfinite(self.flow_ul_per_min) or abs(self.flow_ul_per_min) > MAX_FLOW_UL_PER_MIN:
            raise PumpError(
                f"flow {self.flow_ul_per_min} µL/min exceeds the {MAX_FLOW_UL_PER_MIN:g} µL/min cap"
            )


def delivered_ul(segments: list[Segment]) -> float:
    return sum(segment.duration_s / 60.0 * segment.flow_ul_per_min for segment in segments)


def encode(diameter_mm: float, pitch_mm: float, microsteps: int, segments: list[Segment]) -> str:
    # touch the helpers so a bad diameter fails before a script is sent
    volume_ul_per_revolution(diameter_mm, pitch_mm)
    if isinstance(microsteps, bool) or microsteps not in {1, 2, 4, 8, 16}:
        raise PumpError("microsteps must be 1, 2, 4, 8, or 16")
    lines = [
        f"DIA {diameter_mm:.4f}",
        f"PITCH {pitch_mm:.4f}",
        f"MICRO {microsteps}",
    ]
    for segment in segments:
        Segment(segment.duration_s, segment.flow_ul_per_min)
        lines.append(f"FLOW {segment.flow_ul_per_min:.4f}")
        lines.append(f"RUN {segment.duration_s:.3f}")
    lines.append("STOP")
    script = "\n".join(lines) + "\n"
    simulate(script)  # Reject values that round to an invalid wire representation.
    return script


def simulate(script: str) -> dict:
    """Ideal host-side simulator of the firmware command set."""
    diameter = None
    pitch = None
    micro = None
    flow = 0.0
    volume = 0.0
    steps = 0.0
    for raw in script.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        op = parts[0].upper()
        expected = 1 if op in {"STOP", "STATUS"} else 2
        if len(parts) != expected:
            raise PumpError(f"bad command arity: {line}")
        if len(parts) == 2:
            try:
                value = float(parts[1])
            except ValueError as exc:
                raise PumpError(f"invalid number in {line}") from exc
            if not math.isfinite(value):
                raise PumpError(f"nonfinite number in {line}")
        if op == "DIA" and len(parts) == 2:
            volume_ul_per_revolution(value, 1.0)
            diameter = value
        elif op == "PITCH" and len(parts) == 2:
            volume_ul_per_revolution(10.0, value)
            pitch = value
        elif op == "MICRO" and len(parts) == 2:
            if value not in {1, 2, 4, 8, 16}:
                raise PumpError("microsteps must be 1, 2, 4, 8, or 16")
            micro = int(value)
        elif op == "FLOW" and len(parts) == 2:
            flow = float(parts[1])
            if abs(flow) > MAX_FLOW_UL_PER_MIN:
                raise PumpError("firmware cap: flow too high")
        elif op == "RUN" and len(parts) == 2:
            if None in (diameter, pitch, micro):
                raise PumpError("DIA, PITCH, and MICRO are required before RUN")
            duration = float(parts[1])
            Segment(duration, flow)
            delta = duration / 60.0 * flow
            volume += delta
            steps += steps_for_volume(delta, diameter, pitch, micro)
            # Firmware clears FLOW when a RUN completes.
            flow = 0.0
        elif op == "STOP":
            flow = 0.0
        elif op == "STATUS":
            continue
        else:
            raise PumpError(f"bad command: {line}")
    return {"volume_ul": volume, "steps": steps, "diameter_mm": diameter, "pitch_mm": pitch, "microsteps": micro}
