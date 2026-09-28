import io
import json
import unittest
from unittest.mock import patch

from perfusion.cli import main as cli_main
from perfusion.pump import (
    MAX_FLOW_UL_PER_MIN,
    PumpError,
    Segment,
    delivered_ul,
    encode,
    pulsatile_profile,
    ramp_hold_ramp_profile,
    simulate,
    steps_for_volume,
    validate_firmware_commands,
)


class ProfileTests(unittest.TestCase):
    def test_ramp_hold_ramp_structure_and_integration(self):
        ramp_steps = 4
        segments = ramp_hold_ramp_profile(
            flow_low=10.0,
            flow_high=50.0,
            ramp_up_s=20.0,
            hold_s=40.0,
            ramp_down_s=20.0,
            ramp_steps=ramp_steps,
        )
        self.assertEqual(len(segments), ramp_steps * 2 + 1)
        total_time = sum(s.duration_s for s in segments)
        self.assertAlmostEqual(total_time, 80.0)

        # Check encoded script and firmware validation
        script = encode(14.5, 8.0, 16, segments)
        lines = validate_firmware_commands(script)
        self.assertGreater(len(lines), 10)

        # Verify simulation results match theoretical volume and steps
        result = simulate(script)
        expected_vol = delivered_ul(segments)
        self.assertAlmostEqual(result["volume_ul"], expected_vol, places=4)
        expected_steps = steps_for_volume(expected_vol, 14.5, 8.0, 16)
        self.assertAlmostEqual(result["steps"], expected_steps, places=3)

    def test_ramp_validation_errors(self):
        with self.assertRaises(PumpError):
            ramp_hold_ramp_profile(10, 50, -5, 10, 10)
        with self.assertRaises(PumpError):
            ramp_hold_ramp_profile(10, MAX_FLOW_UL_PER_MIN + 50, 10, 10, 10)
        with self.assertRaises(PumpError):
            ramp_hold_ramp_profile(10, 50, 10, 10, 10, ramp_steps=0)

    def test_pulsatile_profile_and_firmware_validation(self):
        cycles = 5
        segments = pulsatile_profile(
            base_flow=15.0,
            peak_flow=90.0,
            cycle_s=4.0,
            cycles=cycles,
            duty_cycle=0.25,
        )
        self.assertEqual(len(segments), cycles * 2)
        total_duration = sum(s.duration_s for s in segments)
        self.assertAlmostEqual(total_duration, 20.0)

        # Verify pulse segments alternate between peak (1s) and base (3s)
        for i in range(0, len(segments), 2):
            self.assertAlmostEqual(segments[i].duration_s, 1.0)
            self.assertAlmostEqual(segments[i].flow_ul_per_min, 90.0)
            self.assertAlmostEqual(segments[i + 1].duration_s, 3.0)
            self.assertAlmostEqual(segments[i + 1].flow_ul_per_min, 15.0)

        script = encode(12.0, 8.0, 16, segments)
        validated = validate_firmware_commands(script)
        self.assertTrue(any("FLOW 90.0000" in line for line in validated))
        self.assertTrue(any("FLOW 15.0000" in line for line in validated))

        res = simulate(script)
        self.assertAlmostEqual(res["volume_ul"], delivered_ul(segments), places=4)

    def test_pulsatile_validation_errors(self):
        with self.assertRaises(PumpError):
            pulsatile_profile(10, 50, 2.0, 10, duty_cycle=0.0)
        with self.assertRaises(PumpError):
            pulsatile_profile(10, 50, 2.0, 10, duty_cycle=1.0)
        with self.assertRaises(PumpError):
            pulsatile_profile(10, 50, -2.0, 10)
        with self.assertRaises(PumpError):
            pulsatile_profile(10, 50, 2.0, 0)

    def test_firmware_command_validator_rejects_malformed_input(self):
        with self.assertRaises(PumpError):
            validate_firmware_commands("DIA 14.5\nPITCH 8.0\nMICRO 16\nINVALID_OP 10\n")
        with self.assertRaises(PumpError):
            validate_firmware_commands("DIA 14.5\nPITCH 8.0\nMICRO 16\nSTOP extra_arg\n")
        with self.assertRaises(PumpError):
            validate_firmware_commands("DIA 14.5\nPITCH 8.0\nMICRO 16\nFLOW\n")

    def test_cli_ramp_and_pulsatile(self):
        # Test ramp_hold_ramp
        out_ramp = io.StringIO()
        with patch("sys.stdout", out_ramp):
            rc = cli_main([
                "--diameter-mm", "14.5",
                "--profile", "ramp_hold_ramp",
                "--flow-low", "20",
                "--flow-high", "80",
                "--ramp-up-s", "10",
                "--hold-s", "20",
                "--ramp-down-s", "10",
            ])
            self.assertEqual(rc, 0)
        data_ramp = json.loads(out_ramp.getvalue())
        self.assertEqual(data_ramp["profile"], "ramp_hold_ramp")
        self.assertGreater(data_ramp["n_segments"], 5)
        self.assertAlmostEqual(data_ramp["total_duration_s"], 40.0)

        # Test pulsatile
        out_pulse = io.StringIO()
        with patch("sys.stdout", out_pulse):
            rc = cli_main([
                "--diameter-mm", "14.5",
                "--profile", "pulsatile",
                "--base-flow", "10",
                "--peak-flow", "100",
                "--cycle-s", "2",
                "--cycles", "5",
            ])
            self.assertEqual(rc, 0)
        data_pulse = json.loads(out_pulse.getvalue())
        self.assertEqual(data_pulse["profile"], "pulsatile")
        self.assertEqual(data_pulse["n_segments"], 10)
        self.assertAlmostEqual(data_pulse["total_duration_s"], 10.0)


if __name__ == "__main__":
    unittest.main()
