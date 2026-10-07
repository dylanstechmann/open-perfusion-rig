"""Discrete pulse scheduling as the sketch actually performs it.

``simulate`` integrates a continuous flow and reports a fractional step count.
The sketch cannot do that. It computes a step interval in floating point, stores
it in a ``uint32_t`` (truncating to whole microseconds), fires a pulse only when
``micros()`` shows at least that much elapsed since the previous one, counts
whole steps, and ends the run on a ``millis()`` boundary. Each of those is a
quantization, and they do not cancel.

This module reproduces that arithmetic so the three effects can be read
separately:

* **interval truncation** — a shorter stored interval means a faster step rate
  and over-delivery;
* **whole-step remainder** — the final fractional step is never delivered;
* **run-clock truncation** — a requested duration becomes whole milliseconds.

What this still does not model: motor acceleration and pull-out torque, missed
steps under load, backlash, plunger and tubing compliance, pressure, occlusion,
leaks, and the real distribution of loop latency on a given board. A delivered
volume computed here is a scheduling arithmetic result, not a measured volume.
Gravimetric measurement belongs in ``perfusion-calibration-lab``.
"""

from __future__ import annotations

import math

from perfusion.pump import (
    FULL_STEPS,
    MAX_STEP_INTERVAL_US,
    MIN_STEP_INTERVAL_US,
    PumpError,
    Segment,
    volume_ul_per_revolution,
)

# The sketch holds the STEP line high for four microseconds, then does its loop
# work before it can test the clock again. Zero models an ideal scheduler.
DEFAULT_LOOP_OVERHEAD_US = 0.0


def volume_per_step_ul(diameter_mm: float, pitch_mm: float, microsteps: int = 16) -> float:
    """Displacement of one microstep, the smallest volume the rig can deliver."""
    if isinstance(microsteps, bool) or microsteps not in {1, 2, 4, 8, 16}:
        raise PumpError("microsteps must be 1, 2, 4, 8, or 16")
    return volume_ul_per_revolution(diameter_mm, pitch_mm) / (FULL_STEPS * microsteps)


def quantize_interval_us(flow_ul_min: float, diameter_mm: float, pitch_mm: float,
                         microsteps: int = 16) -> dict:
    """Exact and firmware-stored step intervals for one commanded flow.

    The sketch assigns ``stepIntervalUs = (uint32_t)intervalUs``, which truncates
    toward zero rather than rounding, so the stored interval is never longer than
    the exact one and the realized step rate is never slower.
    """
    if not math.isfinite(flow_ul_min) or flow_ul_min == 0:
        raise PumpError("quantization needs a nonzero finite flow")
    per_step = volume_per_step_ul(diameter_mm, pitch_mm, microsteps)
    steps_per_second = abs(flow_ul_min) / 60.0 / per_step
    if not math.isfinite(steps_per_second) or steps_per_second <= 0:
        raise PumpError("requested geometry does not produce a finite step rate")
    exact_us = 1_000_000.0 / steps_per_second
    if exact_us < MIN_STEP_INTERVAL_US:
        raise PumpError("requested flow exceeds the firmware's four-microsecond STEP pulse limit")
    if exact_us > MAX_STEP_INTERVAL_US:
        raise PumpError("requested step interval exceeds the firmware's 32-bit timer range")
    stored_us = float(math.floor(exact_us))
    if stored_us < MIN_STEP_INTERVAL_US:
        raise PumpError("truncated step interval falls below the firmware's pulse limit")
    return {
        "exact_interval_us": exact_us,
        "firmware_interval_us": stored_us,
        "truncated_us": exact_us - stored_us,
        "volume_per_step_ul": per_step,
        "exact_steps_per_second": steps_per_second,
        "firmware_steps_per_second": 1_000_000.0 / stored_us,
        "rate_inflation": exact_us / stored_us,
    }


def quantized_run(flow_ul_min: float, duration_s: float, diameter_mm: float, pitch_mm: float,
                  microsteps: int = 16, *, loop_overhead_us: float = DEFAULT_LOOP_OVERHEAD_US) -> dict:
    """Simulate one RUN segment under the sketch's integer scheduling.

    ``loop_overhead_us`` adds a fixed delay to every interval, standing in for the
    4 µs pulse plus loop work. The sketch can only fire late, never early, so
    overhead always reduces delivery. It is a stated assumption, not a measured
    board latency.
    """
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise PumpError("duration must be a positive finite number of seconds")
    if not math.isfinite(loop_overhead_us) or loop_overhead_us < 0:
        raise PumpError("loop_overhead_us must be finite and nonnegative")
    interval = quantize_interval_us(flow_ul_min, diameter_mm, pitch_mm, microsteps)
    direction = 1.0 if flow_ul_min > 0 else -1.0

    # The sketch stores the run length as whole milliseconds: (uint32_t)(seconds * 1000).
    commanded_ms = int(duration_s * 1000.0)
    effective_interval_us = interval["firmware_interval_us"] + loop_overhead_us
    # millis() >= runDurationMs ends the run, so pulses occur while elapsed < duration.
    steps = int(math.floor(commanded_ms * 1000.0 / effective_interval_us))
    delivered = direction * steps * interval["volume_per_step_ul"]
    continuous = duration_s / 60.0 * flow_ul_min

    # Volume the schedule would deliver with an untruncated interval over the same
    # commanded window, isolating interval truncation from the whole-step remainder.
    ideal_steps = commanded_ms * 1000.0 / interval["exact_interval_us"]
    return {
        **interval,
        "commanded_flow_ul_min": float(flow_ul_min),
        "commanded_duration_s": float(duration_s),
        "firmware_duration_ms": commanded_ms,
        "run_clock_truncation_s": duration_s - commanded_ms / 1000.0,
        "loop_overhead_us": float(loop_overhead_us),
        "effective_interval_us": effective_interval_us,
        "steps_delivered": steps,
        "fractional_steps_requested": ideal_steps,
        "unfired_fractional_step": ideal_steps - math.floor(ideal_steps),
        "delivered_ul": delivered,
        "continuous_model_ul": continuous,
        "volume_error_ul": delivered - continuous,
        "relative_volume_error": (delivered - continuous) / continuous if continuous else None,
        "mean_realized_flow_ul_min": (delivered / duration_s * 60.0) if duration_s else None,
        "seconds_per_step": effective_interval_us / 1_000_000.0,
    }


def flow_ripple(result: dict) -> dict:
    """Describe the within-interval flow the discrete schedule actually produces.

    Volume arrives in one-step increments, so the instantaneous flow is a spike at
    each pulse and zero between pulses. Averaging over a window shorter than one
    step interval therefore gives either zero or a large value; the commanded flow
    is only meaningful averaged over many steps.
    """
    per_step = result["volume_per_step_ul"]
    interval_s = result["effective_interval_us"] / 1_000_000.0
    windows = {}
    for label, window_s in (("one_step_interval", interval_s), ("one_second", 1.0),
                            ("one_minute", 60.0)):
        steps_in_window = window_s / interval_s
        windows[label] = {
            "window_s": window_s,
            "steps_in_window": steps_in_window,
            "quantization_fraction_of_window_volume":
                1.0 / steps_in_window if steps_in_window else None,
        }
    return {
        "volume_per_step_ul": per_step,
        "step_interval_s": interval_s,
        "delivery_pattern": "one discrete displacement per pulse; no flow between pulses",
        "windows": windows,
        "limitations": [
            "The pattern described here is the step schedule only. Fluid inertia, tubing and "
            "plunger compliance smooth real delivery to an unknown degree.",
            "A commanded flow is an average over many steps. Over one step interval the "
            "delivered flow is either zero or one whole step's displacement.",
            "No motor dynamics, missed steps, backlash, pressure or occlusion are modeled.",
        ],
    }


def quantization_report(segments: list[Segment], diameter_mm: float, pitch_mm: float,
                        microsteps: int = 16, *,
                        loop_overhead_us: float = DEFAULT_LOOP_OVERHEAD_US) -> dict:
    """Quantization summary for a whole profile, segment by segment.

    Zero-flow segments are included as explicit idle time: the sketch disables the
    driver and emits no pulses, so they deliver nothing and are not errors.
    """
    if not segments:
        raise PumpError("a quantization report needs at least one segment")
    rows, total_delivered, total_continuous, total_steps = [], 0.0, 0.0, 0
    for index, segment in enumerate(segments):
        if segment.flow_ul_per_min == 0:
            rows.append({"segment": index, "commanded_flow_ul_min": 0.0,
                         "commanded_duration_s": segment.duration_s, "steps_delivered": 0,
                         "delivered_ul": 0.0, "continuous_model_ul": 0.0,
                         "volume_error_ul": 0.0, "status": "idle_no_pulses"})
            continue
        row = quantized_run(segment.flow_ul_per_min, segment.duration_s, diameter_mm, pitch_mm,
                            microsteps, loop_overhead_us=loop_overhead_us)
        row.update({"segment": index, "status": "stepping"})
        rows.append(row)
        total_delivered += row["delivered_ul"]
        total_continuous += row["continuous_model_ul"]
        total_steps += row["steps_delivered"]
    stepping = [row for row in rows if row["status"] == "stepping"]
    return {
        "schema_version": 1,
        "model": "sketch integer step scheduling: uint32 interval truncation, whole steps, "
                 "millisecond run clock",
        "geometry": {"diameter_mm": diameter_mm, "pitch_mm": pitch_mm, "microsteps": microsteps,
                     "volume_per_step_ul": volume_per_step_ul(diameter_mm, pitch_mm, microsteps)},
        "loop_overhead_us": float(loop_overhead_us),
        "n_segments": len(rows),
        "n_stepping_segments": len(stepping),
        "total_steps": total_steps,
        "total_delivered_ul": total_delivered,
        "total_continuous_model_ul": total_continuous,
        "total_volume_error_ul": total_delivered - total_continuous,
        "total_relative_volume_error": ((total_delivered - total_continuous) / total_continuous
                                        if total_continuous else None),
        "worst_segment_relative_error": (
            max((abs(row["relative_volume_error"]) for row in stepping
                 if row["relative_volume_error"] is not None), default=None)),
        "segments": rows,
        "flow_ripple": flow_ripple(stepping[0]) if stepping else None,
        "limitations": [
            "Interval truncation, whole steps and the millisecond run clock are reproduced from "
            "the sketch's arithmetic. They are not the only sources of delivery error.",
            "Loop overhead is a stated assumption. The sketch can fire a pulse late but never "
            "early, so real latency moves delivery down from the zero-overhead case.",
            "Motor acceleration, pull-out torque, missed steps, backlash, compliance, pressure, "
            "occlusion and leaks are not modeled.",
            "No hardware was operated. These are arithmetic results, not measured volumes; "
            "measure delivery gravimetrically before trusting any number here.",
        ],
    }
