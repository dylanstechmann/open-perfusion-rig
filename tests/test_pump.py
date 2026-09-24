import math
import unittest

from perfusion.pump import (
    MAX_FLOW_UL_PER_MIN,
    PumpError,
    Segment,
    delivered_ul,
    diameter_from_water_mass,
    encode,
    simulate,
    steps_for_volume,
    volume_ul_per_revolution,
)


class PumpTests(unittest.TestCase):
    def test_cylinder_volume(self):
        # 10 mm travel of a 10 mm diameter syringe is 785.4 µL
        per_rev = volume_ul_per_revolution(10.0, 10.0)
        self.assertAlmostEqual(per_rev, math.pi * 25.0 * 10.0, places=6)

    def test_calibration_inverts_the_cylinder(self):
        expected = volume_ul_per_revolution(14.5, 8.0)  # µL per 8 mm of a 14.5 mm ID
        # that volume was delivered over one pitch of travel
        recovered = diameter_from_water_mass(expected, 8.0)
        self.assertAlmostEqual(recovered, 14.5, places=6)

    def test_script_matches_integrated_volume(self):
        segments = [
            Segment(30 * 60, 50),
            Segment(10 * 60, -20),
        ]
        script = encode(14.5, 8.0, 16, segments)
        result = simulate(script)
        self.assertAlmostEqual(result["volume_ul"], delivered_ul(segments), places=4)
        self.assertAlmostEqual(
            result["steps"],
            steps_for_volume(result["volume_ul"], 14.5, 8.0, 16),
            places=3,
        )

    def test_flow_cap(self):
        with self.assertRaises(PumpError):
            Segment(10, MAX_FLOW_UL_PER_MIN + 1)

    def test_bad_command_rejected(self):
        with self.assertRaises(PumpError):
            simulate("DIA 14.5\nRUN 10\n")


if __name__ == "__main__":
    unittest.main()
