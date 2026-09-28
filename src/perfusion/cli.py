"""Print a command script for constant, multi-segment ramp-hold-ramp, or pulsatile perfusion profiles."""

from __future__ import annotations

import argparse
import json
import sys

from perfusion.pump import (
    PumpError,
    Segment,
    delivered_ul,
    encode,
    pulsatile_profile,
    ramp_hold_ramp_profile,
    simulate,
    validate_firmware_commands,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Encode an in-vitro syringe-pump script")
    parser.add_argument("--diameter-mm", type=float, required=True, help="syringe barrel inner diameter in mm")
    parser.add_argument("--pitch-mm", type=float, default=8.0, help="leadscrew pitch in mm/rev (default: 8.0)")
    parser.add_argument("--microsteps", type=int, default=16, help="microstepping factor (default: 16)")
    parser.add_argument(
        "--profile",
        choices=["constant", "ramp_hold_ramp", "pulsatile"],
        default="constant",
        help="flow profile mode: constant (default), ramp_hold_ramp, or pulsatile",
    )

    # Constant flow arguments
    parser.add_argument("--flow", type=float, help="µL/min, signed (required for constant profile)")
    parser.add_argument("--minutes", type=float, help="duration in minutes (required for constant profile)")

    # Ramp-hold-ramp arguments
    parser.add_argument("--flow-low", type=float, default=10.0, help="ramp baseline flow in µL/min (default: 10.0)")
    parser.add_argument("--flow-high", type=float, default=100.0, help="ramp peak flow in µL/min (default: 100.0)")
    parser.add_argument("--ramp-up-s", type=float, default=30.0, help="ramp-up duration in seconds (default: 30.0)")
    parser.add_argument("--hold-s", type=float, default=60.0, help="hold duration in seconds (default: 60.0)")
    parser.add_argument("--ramp-down-s", type=float, default=30.0, help="ramp-down duration in seconds (default: 30.0)")
    parser.add_argument("--ramp-steps", type=int, default=5, help="discrete steps per ramp (default: 5)")

    # Pulsatile arguments
    parser.add_argument("--base-flow", type=float, default=10.0, help="pulsatile base flow in µL/min (default: 10.0)")
    parser.add_argument("--peak-flow", type=float, default=150.0, help="pulsatile peak flow in µL/min (default: 150.0)")
    parser.add_argument("--cycle-s", type=float, default=2.0, help="pulsatile cycle duration in seconds (default: 2.0)")
    parser.add_argument("--cycles", type=int, default=20, help="number of pulsatile cycles (default: 20)")
    parser.add_argument("--duty-cycle", type=float, default=0.5, help="pulsatile duty cycle (0-1, default: 0.5)")

    args = parser.parse_args(argv)

    try:
        if args.profile == "constant":
            if args.flow is None or args.minutes is None:
                parser.error("--flow and --minutes are required when --profile is 'constant'")
            segments = [Segment(duration_s=args.minutes * 60.0, flow_ul_per_min=args.flow)]
        elif args.profile == "ramp_hold_ramp":
            segments = ramp_hold_ramp_profile(
                flow_low=args.flow_low,
                flow_high=args.flow_high,
                ramp_up_s=args.ramp_up_s,
                hold_s=args.hold_s,
                ramp_down_s=args.ramp_down_s,
                ramp_steps=args.ramp_steps,
            )
        elif args.profile == "pulsatile":
            segments = pulsatile_profile(
                base_flow=args.base_flow,
                peak_flow=args.peak_flow,
                cycle_s=args.cycle_s,
                cycles=args.cycles,
                duty_cycle=args.duty_cycle,
            )
        else:
            parser.error(f"unknown profile: {args.profile}")

        script = encode(args.diameter_mm, args.pitch_mm, args.microsteps, segments)
        validated_lines = validate_firmware_commands(script)
        sim_res = simulate(script)
    except PumpError as exc:
        parser.error(str(exc))

    report = {
        "profile": args.profile,
        "n_segments": len(segments),
        "total_duration_s": round(sum(s.duration_s for s in segments), 3),
        "delivered_ul": round(delivered_ul(segments), 4),
        "simulation": sim_res,
        "validated_command_count": len(validated_lines),
        "script": script,
        "fluid_path": "sterile syringe and purchased tubing only; the printed carriage pushes the plunger",
    }
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

