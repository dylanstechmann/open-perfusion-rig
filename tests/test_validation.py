import unittest

from perfusion.pump import PumpError, Segment, diameter_from_water_mass, encode, simulate


class ValidationTests(unittest.TestCase):
    def test_nonfinite_inputs_and_negative_run_are_rejected(self):
        for duration, flow in [(float("nan"), 5), (5, float("nan")), (5, float("inf")), (-1, 5)]:
            with self.assertRaises(PumpError):
                Segment(duration, flow)
        for command in ["RUN -1", "RUN nan", "FLOW inf", "PITCH 0", "MICRO 1.5", "STOP 99"]:
            with self.assertRaises(PumpError):
                simulate("DIA 14.5\nPITCH 8\nMICRO 16\n" + command)

    def test_completed_run_clears_flow(self):
        result = simulate("DIA 14.5\nPITCH 8\nMICRO 16\nFLOW 60\nRUN 10\nRUN 10\n")
        self.assertAlmostEqual(result["volume_ul"], 10)

    def test_density_correction(self):
        unit = diameter_from_water_mass(100, 10)
        corrected = diameter_from_water_mass(100, 10, density_mg_ul=0.81)
        self.assertAlmostEqual(corrected, unit / 0.9)

    def test_wire_rounding_cannot_make_run_zero(self):
        with self.assertRaises(PumpError):
            encode(14.5, 8, 16, [Segment(0.00001, 50)])

    def test_host_rejects_nonzero_flow_below_firmware_deadband(self):
        for flow in [0.009999, -0.009999, 0.005, -0.005]:
            with self.assertRaisesRegex(PumpError, "firmware disables the motor"):
                Segment(10, flow)
            with self.assertRaisesRegex(PumpError, "below 0.01"):
                simulate(f"DIA 14.5\nPITCH 8\nMICRO 16\nFLOW {flow}\nRUN 10\n")

    def test_zero_and_deadband_boundary_keep_firmware_semantics(self):
        self.assertEqual(simulate("DIA 14.5\nPITCH 8\nMICRO 16\nFLOW 0\nRUN 10\n")["volume_ul"], 0)
        self.assertGreater(
            simulate("DIA 14.5\nPITCH 8\nMICRO 16\nFLOW 0.01\nRUN 10\n")["volume_ul"],
            0,
        )

    def test_host_rejects_step_rates_the_firmware_cannot_schedule(self):
        with self.assertRaisesRegex(PumpError, "four-microsecond STEP pulse"):
            simulate("DIA 1\nPITCH 0.00001\nMICRO 16\nFLOW 2000\nRUN 1\n")
        with self.assertRaisesRegex(PumpError, "32-bit timer range"):
            simulate("DIA 40\nPITCH 1e38\nMICRO 16\nFLOW 0.01\nRUN 1\n")
