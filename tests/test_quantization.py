from __future__ import annotations

import math
import unittest

from perfusion.pump import PumpError, Segment, volume_ul_per_revolution
from perfusion.quantization import (
    flow_ripple,
    quantization_report,
    quantize_interval_us,
    quantized_run,
    volume_per_step_ul,
)

DIAMETER_MM = 14.5
PITCH_MM = 8.0
MICROSTEPS = 16


class StepGeometryTests(unittest.TestCase):
    def test_volume_per_step_is_one_revolution_over_the_step_count(self):
        per_revolution = volume_ul_per_revolution(DIAMETER_MM, PITCH_MM)
        self.assertAlmostEqual(volume_per_step_ul(DIAMETER_MM, PITCH_MM, 16),
                               per_revolution / (200 * 16), places=12)
        # Finer microstepping delivers proportionally smaller increments.
        self.assertAlmostEqual(volume_per_step_ul(DIAMETER_MM, PITCH_MM, 1),
                               volume_per_step_ul(DIAMETER_MM, PITCH_MM, 16) * 16, places=12)

    def test_unsupported_microstepping_is_rejected(self):
        for bad in (0, 3, 32, True):
            with self.subTest(bad=bad):
                with self.assertRaises(PumpError):
                    volume_per_step_ul(DIAMETER_MM, PITCH_MM, bad)


class IntervalTruncationTests(unittest.TestCase):
    def test_stored_interval_truncates_and_never_slows_the_rate(self):
        for flow in (0.5, 5.0, 50.0, 500.0, 1500.0):
            with self.subTest(flow=flow):
                result = quantize_interval_us(flow, DIAMETER_MM, PITCH_MM, MICROSTEPS)
                self.assertEqual(result["firmware_interval_us"],
                                 math.floor(result["exact_interval_us"]))
                self.assertLessEqual(result["firmware_interval_us"], result["exact_interval_us"])
                self.assertGreaterEqual(result["rate_inflation"], 1.0)
                self.assertGreaterEqual(result["firmware_steps_per_second"],
                                        result["exact_steps_per_second"])

    def test_truncation_matters_more_at_short_intervals(self):
        slow = quantize_interval_us(5.0, DIAMETER_MM, PITCH_MM, MICROSTEPS)
        fast = quantize_interval_us(1500.0, DIAMETER_MM, PITCH_MM, MICROSTEPS)
        self.assertLess(slow["rate_inflation"] - 1.0, fast["rate_inflation"] - 1.0)

    def test_the_firmware_limits_are_enforced_on_the_quantized_interval(self):
        with self.assertRaisesRegex(PumpError, "nonzero finite flow"):
            quantize_interval_us(0.0, DIAMETER_MM, PITCH_MM, MICROSTEPS)
        with self.assertRaises(PumpError):
            quantize_interval_us(float("inf"), DIAMETER_MM, PITCH_MM, MICROSTEPS)
        # The slowest allowed flow through a wide barrel at full steps exceeds the
        # firmware's 32-bit timer. The four-microsecond pulse floor is unreachable
        # within the allowed geometry and the 2000 uL/min cap, so only the upper
        # bound can actually be tripped from the command interface.
        with self.assertRaisesRegex(PumpError, "32-bit timer range"):
            quantize_interval_us(0.01, 20.0, PITCH_MM, 1)


class QuantizedRunTests(unittest.TestCase):
    def test_delivery_is_a_whole_number_of_steps(self):
        result = quantized_run(50.0, 1800.0, DIAMETER_MM, PITCH_MM, MICROSTEPS)
        per_step = result["volume_per_step_ul"]
        self.assertEqual(result["steps_delivered"], 3633)
        self.assertAlmostEqual(result["delivered_ul"], result["steps_delivered"] * per_step, places=12)
        self.assertAlmostEqual(result["continuous_model_ul"], 1500.0, places=9)
        # Under-delivery here: the unfired fractional step outweighs interval truncation.
        self.assertLess(result["delivered_ul"], result["continuous_model_ul"])
        self.assertAlmostEqual(result["relative_volume_error"], -1.381e-4, delta=1e-6)

    def test_negative_flow_delivers_negative_volume_with_the_same_step_count(self):
        forward = quantized_run(50.0, 600.0, DIAMETER_MM, PITCH_MM, MICROSTEPS)
        reverse = quantized_run(-50.0, 600.0, DIAMETER_MM, PITCH_MM, MICROSTEPS)
        self.assertEqual(forward["steps_delivered"], reverse["steps_delivered"])
        self.assertAlmostEqual(forward["delivered_ul"], -reverse["delivered_ul"], places=12)

    def test_whole_step_remainder_dominates_at_low_flow(self):
        # One step takes about 2.5 s at 10 uL/min, so a 60 s run loses a large fraction.
        result = quantized_run(10.0, 60.0, DIAMETER_MM, PITCH_MM, MICROSTEPS)
        self.assertEqual(result["steps_delivered"], 24)
        self.assertGreater(abs(result["relative_volume_error"]), 1e-3)
        self.assertGreater(result["seconds_per_step"], 1.0)

    def test_run_clock_truncates_to_whole_milliseconds(self):
        result = quantized_run(100.0, 1.0005, DIAMETER_MM, PITCH_MM, MICROSTEPS)
        self.assertEqual(result["firmware_duration_ms"], 1000)
        self.assertAlmostEqual(result["run_clock_truncation_s"], 0.0005, places=9)

    def test_loop_overhead_can_only_reduce_delivery(self):
        ideal = quantized_run(1500.0, 10.0, DIAMETER_MM, PITCH_MM, MICROSTEPS)
        delayed = quantized_run(1500.0, 10.0, DIAMETER_MM, PITCH_MM, MICROSTEPS,
                                loop_overhead_us=50.0)
        self.assertLess(delayed["steps_delivered"], ideal["steps_delivered"])
        self.assertLess(abs(delayed["delivered_ul"]), abs(ideal["delivered_ul"]))
        self.assertEqual(delayed["loop_overhead_us"], 50.0)
        # At a 2.5 s interval the same overhead is negligible.
        slow_ideal = quantized_run(10.0, 600.0, DIAMETER_MM, PITCH_MM, MICROSTEPS)
        slow_delayed = quantized_run(10.0, 600.0, DIAMETER_MM, PITCH_MM, MICROSTEPS,
                                     loop_overhead_us=50.0)
        self.assertEqual(slow_ideal["steps_delivered"], slow_delayed["steps_delivered"])

    def test_invalid_run_settings_are_rejected(self):
        for kwargs in ({"duration_s": 0.0}, {"duration_s": -1.0}, {"duration_s": float("nan")}):
            with self.subTest(**kwargs):
                with self.assertRaises(PumpError):
                    quantized_run(50.0, kwargs["duration_s"], DIAMETER_MM, PITCH_MM, MICROSTEPS)
        with self.assertRaises(PumpError):
            quantized_run(50.0, 60.0, DIAMETER_MM, PITCH_MM, MICROSTEPS, loop_overhead_us=-1.0)


class FlowRippleTests(unittest.TestCase):
    def test_ripple_describes_discrete_delivery_windows(self):
        result = quantized_run(10.0, 600.0, DIAMETER_MM, PITCH_MM, MICROSTEPS)
        ripple = flow_ripple(result)
        self.assertEqual(ripple["windows"]["one_step_interval"]["steps_in_window"], 1.0)
        self.assertAlmostEqual(
            ripple["windows"]["one_minute"]["steps_in_window"],
            60.0 / ripple["step_interval_s"], places=9)
        self.assertIn("no flow between pulses", ripple["delivery_pattern"])
        joined = " ".join(ripple["limitations"])
        self.assertIn("backlash", joined)
        self.assertIn("either zero or one whole step", joined)


class ProfileReportTests(unittest.TestCase):
    def test_idle_segments_deliver_nothing_and_are_not_errors(self):
        report = quantization_report(
            [Segment(60.0, 10.0), Segment(30.0, 0.0), Segment(60.0, 25.0)],
            DIAMETER_MM, PITCH_MM, MICROSTEPS)
        self.assertEqual(report["n_segments"], 3)
        self.assertEqual(report["n_stepping_segments"], 2)
        idle = report["segments"][1]
        self.assertEqual(idle["status"], "idle_no_pulses")
        self.assertEqual(idle["steps_delivered"], 0)
        self.assertEqual(idle["volume_error_ul"], 0.0)

    def test_totals_match_the_sum_of_stepping_segments(self):
        segments = [Segment(120.0, 30.0), Segment(45.0, 0.0), Segment(90.0, 75.0)]
        report = quantization_report(segments, DIAMETER_MM, PITCH_MM, MICROSTEPS)
        stepping = [row for row in report["segments"] if row["status"] == "stepping"]
        self.assertEqual(report["total_steps"], sum(row["steps_delivered"] for row in stepping))
        self.assertAlmostEqual(report["total_delivered_ul"],
                               sum(row["delivered_ul"] for row in stepping), places=12)
        self.assertAlmostEqual(report["total_continuous_model_ul"],
                               sum(row["continuous_model_ul"] for row in stepping), places=12)
        self.assertEqual(report["worst_segment_relative_error"],
                         max(abs(row["relative_volume_error"]) for row in stepping))

    def test_report_states_what_it_does_not_model(self):
        report = quantization_report([Segment(60.0, 20.0)], DIAMETER_MM, PITCH_MM, MICROSTEPS)
        joined = " ".join(report["limitations"])
        for absent in ("backlash", "occlusion", "No hardware was operated"):
            self.assertIn(absent, joined)
        self.assertIn("uint32 interval truncation", report["model"])

    def test_empty_profile_is_rejected(self):
        with self.assertRaises(PumpError):
            quantization_report([], DIAMETER_MM, PITCH_MM, MICROSTEPS)


class CliQuantizationTests(unittest.TestCase):
    def test_cli_emits_the_quantization_block_only_when_asked(self):
        import contextlib
        import io
        import json

        from perfusion.cli import main

        base = ["--diameter-mm", "14.5", "--pitch-mm", "8", "--microsteps", "16",
                "--flow", "50", "--minutes", "30"]
        plain = io.StringIO()
        with contextlib.redirect_stdout(plain):
            self.assertEqual(main(base), 0)
        self.assertNotIn("quantization", json.loads(plain.getvalue()))

        detailed = io.StringIO()
        with contextlib.redirect_stdout(detailed):
            self.assertEqual(main([*base, "--quantization", "--loop-overhead-us", "4"]), 0)
        report = json.loads(detailed.getvalue())
        quantization = report["quantization"]
        self.assertEqual(quantization["loop_overhead_us"], 4.0)
        self.assertEqual(quantization["n_stepping_segments"], 1)
        # The continuous simulation and the discrete schedule disagree, by design.
        self.assertNotEqual(round(report["delivered_ul"], 6),
                            round(quantization["total_delivered_ul"], 6))
        self.assertLess(abs(quantization["total_relative_volume_error"]), 1e-2)


if __name__ == "__main__":
    unittest.main()
