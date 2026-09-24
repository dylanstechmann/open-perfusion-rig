"""Print a command script for a simple perfusion profile."""

from __future__ import annotations

import argparse
import json
import sys

from perfusion.pump import Segment, delivered_ul, encode, simulate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Encode an in-vitro syringe-pump script")
    parser.add_argument("--diameter-mm", type=float, required=True)
    parser.add_argument("--pitch-mm", type=float, default=8.0)
    parser.add_argument("--microsteps", type=int, default=16)
    parser.add_argument("--flow", type=float, required=True, help="µL/min, signed")
    parser.add_argument("--minutes", type=float, required=True)
    args = parser.parse_args(argv)
    segments = [Segment(duration_s=args.minutes * 60.0, flow_ul_per_min=args.flow)]
    script = encode(args.diameter_mm, args.pitch_mm, args.microsteps, segments)
    report = {
        "delivered_ul": delivered_ul(segments),
        "simulation": simulate(script),
        "script": script,
        "fluid_path": "sterile syringe and purchased tubing only; the printed carriage pushes the plunger",
    }
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
