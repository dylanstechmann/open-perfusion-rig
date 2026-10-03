import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "firmware_host" / "firmware_harness.cpp"


class FirmwareHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("g++")
        if not compiler:
            raise unittest.SkipTest("native g++ compiler is unavailable")
        cls._temp = tempfile.TemporaryDirectory()
        cls.binary = Path(cls._temp.name) / "firmware_harness"
        compiled = subprocess.run(
            [
                compiler,
                "-std=c++17",
                "-Wall",
                "-Wextra",
                "-I",
                str(HARNESS.parent),
                str(HARNESS),
                "-o",
                str(cls.binary),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if compiled.returncode:
            raise AssertionError(f"firmware harness did not compile:\n{compiled.stdout}\n{compiled.stderr}")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "_temp"):
            cls._temp.cleanup()

    def run_scenario(self, name):
        result = subprocess.run([str(self.binary), name], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, msg=f"{result.stdout}\n{result.stderr}")

    def test_firmware_parser_rejects_malformed_values_and_arity(self):
        self.run_scenario("reject-invalid")

    def test_firmware_rejects_step_rate_below_supported_interval(self):
        self.run_scenario("reject-pulse-rate")

    def test_firmware_rejects_flow_below_deadband(self):
        self.run_scenario("reject-deadband")

    def test_firmware_reports_run_completion_and_disables_driver(self):
        self.run_scenario("complete-run")

    def test_firmware_emits_one_bounded_step_pulse(self):
        self.run_scenario("step-pulse")


if __name__ == "__main__":
    unittest.main()
