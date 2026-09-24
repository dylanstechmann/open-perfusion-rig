"""Displacement math for a leadscrew syringe pusher.

The fluid path is the sterile syringe and purchased tubing. Printed parts
push the plunger. They do not touch the medium.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

FULL_STEPS = 200
MAX_FLOW_UL_PER_MIN = 2000.0


class PumpError(ValueError):
    pass


def volume_ul_per_revolution(diameter_mm: float, pitch_mm: float) -> float:
    if diameter_mm <= 0 or pitch_mm <= 0:
        raise PumpError("diameter and pitch must be positive")
    if not 1.0 <= diameter_mm <= 40.0:
        raise PumpError("diameter looks like the wrong unit or the wrong syringe")
    radius = diameter_mm / 2.0
    return math.pi * radius * radius * pitch_mm


def diameter_from_water_mass(mass_mg: float, travel_mm: float) -> float:
    """1 mg of water is 1 µL. Measure a real extrusion; do not trust a catalog ID."""
    if mass_mg <= 0 or travel_mm <= 0:
        raise PumpError("calibration inputs must be positive")
    radius = math.sqrt(mass_mg / (math.pi * travel_mm))
    return 2.0 * radius


def steps_for_volume(volume_ul: float, diameter_mm: float, pitch_mm: float, microsteps: int = 16) -> float:
    if microsteps not in {1, 2, 4, 8, 16}:
        raise PumpError("microsteps must be 1, 2, 4, 8, or 16")
    per_rev = volume_ul_per_revolution(diameter_mm, pitch_mm)
    return volume_ul / per_rev * FULL_STEPS * microsteps


@dataclass
class Segment:
    duration_s: float
    flow_ul_per_min: float

    def __post_init__(self):
        if self.duration_s <= 0:
            raise PumpError("duration must be positive")
        if abs(self.flow_ul_per_min) > MAX_FLOW_UL_PER_MIN:
            raise PumpError(
                f"flow {self.flow_ul_per_min} µL/min exceeds the {MAX_FLOW_UL_PER_MIN:g} µL/min cap"
            )


def delivered_ul(segments: list[Segment]) -> float:
    return sum(segment.duration_s / 60.0 * segment.flow_ul_per_min for segment in segments)


def encode(diameter_mm: float, pitch_mm: float, microsteps: int, segments: list[Segment]) -> str:
    # touch the helpers so a bad diameter fails before a script is sent
    volume_ul_per_revolution(diameter_mm, pitch_mm)
    if microsteps not in {1, 2, 4, 8, 16}:
        raise PumpError("microsteps must be 1, 2, 4, 8, or 16")
    lines = [
        f"DIA {diameter_mm:.4f}",
        f"PITCH {pitch_mm:.4f}",
        f"MICRO {microsteps}",
    ]
    for segment in segments:
        lines.append(f"FLOW {segment.flow_ul_per_min:.4f}")
        lines.append(f"RUN {segment.duration_s:.3f}")
    lines.append("STOP")
    return "\n".join(lines) + "\n"


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
        if op == "DIA" and len(parts) == 2:
            diameter = float(parts[1])
        elif op == "PITCH" and len(parts) == 2:
            pitch = float(parts[1])
        elif op == "MICRO" and len(parts) == 2:
            micro = int(parts[1])
        elif op == "FLOW" and len(parts) == 2:
            flow = float(parts[1])
            if abs(flow) > MAX_FLOW_UL_PER_MIN:
                raise PumpError("firmware cap: flow too high")
        elif op == "RUN" and len(parts) == 2:
            if None in (diameter, pitch, micro):
                raise PumpError("DIA, PITCH, and MICRO are required before RUN")
            duration = float(parts[1])
            delta = duration / 60.0 * flow
            volume += delta
            steps += steps_for_volume(delta, diameter, pitch, micro)
        elif op == "STOP":
            flow = 0.0
        elif op == "STATUS":
            continue
        else:
            raise PumpError(f"bad command: {line}")
    return {"volume_ul": volume, "steps": steps, "diameter_mm": diameter, "pitch_mm": pitch, "microsteps": micro}
