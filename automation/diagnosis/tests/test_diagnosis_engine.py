import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from automation.diagnosis.diagnosis_engine import diagnose


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REFERENCE_EVIDENCE_DIR = REPOSITORY_ROOT / "evidence" / "day2" / "diagnostic"


def check(name, status, **metadata):
    return {"name": name, "status": status, **metadata}


def evidence(overrides=None):
    layers = {
        "hardware": [
            check("system_health", "PASS"),
            check("power_state", "PASS"),
            check("storage_health", "PASS"),
            check("post_status", "PASS"),
        ],
        "boot": [check("boot_state", "PASS")],
        "network": [
            check("nic_link", "PASS"),
            check("ip_address", "PASS"),
            check("gateway", "PASS"),
            check("routes", "PASS"),
        ],
        "service": [
            check("process", "PASS"),
            check("listening_port", "PASS"),
            check("http_health", "PASS"),
        ],
    }
    layers.update(overrides or {})
    return {
        "host": "test-host",
        "generated_at": "2026-08-25T00:00:00Z",
        "results": [
            {"category": layer, "checks": layer_checks}
            for layer, layer_checks in layers.items()
        ],
    }


class DiagnosisRuleTests(unittest.TestCase):
    def assert_rule(self, data, rule_id):
        result = diagnose(data)
        self.assertEqual(result["rule_id"], rule_id)
        for item in result["matched_evidence"]:
            self.assertEqual(set(item), {"layer", "check_name", "result"})
        return result

    def test_01_hardware_storage_explicit_fail(self):
        data = evidence(
            {
                "hardware": [
                    check("storage_health", "FAIL"),
                    check(
                        "storage_iml_event",
                        "CRITICAL",
                        created="2026-08-25T00:01:00Z",
                    ),
                ]
            }
        )
        data["incident_started_at"] = "2026-08-25T00:00:00Z"
        self.assert_rule(data, "HW-STORAGE-01")

    def test_02_hardware_unknown_does_not_match(self):
        result = diagnose(evidence({"hardware": [check("storage_health", "UNKNOWN")]}))
        self.assertIsNone(result["rule_id"])
        self.assertEqual(result["diagnosis_status"], "INSUFFICIENT_EVIDENCE")

    def test_03_boot_os_failure_with_prerequisites(self):
        data = evidence(
            {
                "hardware": [
                    check("system_health", "PASS"),
                    check("power_state", "PASS"),
                    check("storage_health", "PASS"),
                    check("post_status", "PASS"),
                ],
                "boot": [check("boot_state", "FAIL")],
            }
        )
        self.assert_rule(data, "BOOT-OS-01")

    def test_04_boot_failure_without_prerequisites_does_not_match(self):
        result = diagnose(
            evidence(
                {
                    "hardware": [check("storage_health", "PASS")],
                    "boot": [check("boot_state", "FAIL")],
                }
            )
        )
        self.assertIsNone(result["rule_id"])
        self.assertEqual(result["diagnosis_status"], "INSUFFICIENT_EVIDENCE")

    def test_05_nic_and_gateway_fail_does_not_match_route(self):
        data = evidence(
            {
                "network": [
                    check("nic_link", "FAIL"),
                    check("ip_address", "PASS"),
                    check("gateway", "FAIL"),
                    check("routes", "PASS"),
                ]
            }
        )
        self.assertIsNone(diagnose(data)["rule_id"])

    def test_06_nic_ip_pass_and_gateway_fails(self):
        data = evidence(
            {
                "network": [
                    check("nic_link", "PASS"),
                    check("ip_address", "PASS"),
                    check("gateway", "FAIL"),
                    check("routes", "PASS"),
                ]
            }
        )
        result = self.assert_rule(data, "NET-ROUTE-01")
        self.assertEqual(
            {item["check_name"] for item in result["matched_evidence"]},
            {"nic_link", "ip_address", "gateway", "routes"},
        )

    def test_07_network_failure_precedes_service_failure(self):
        data = evidence(
            {
                "network": [
                    check("nic_link", "PASS"),
                    check("ip_address", "PASS"),
                    check("gateway", "PASS"),
                    check("routes", "FAIL"),
                ],
                "service": [
                    check("process", "PASS"),
                    check("listening_port", "PASS"),
                    check("http_health", "FAIL"),
                ],
            }
        )
        self.assert_rule(data, "NET-ROUTE-01")

    def test_08_network_pass_and_process_fails(self):
        data = evidence(
            {
                "service": [
                    check("process", "FAIL"),
                    check("listening_port", "PASS"),
                    check("http_health", "PASS"),
                ]
            }
        )
        self.assert_rule(data, "SVC-HTTP-01")

    def test_09_network_pass_and_listening_port_fails(self):
        data = evidence(
            {
                "service": [
                    check("process", "PASS"),
                    check("listening_port", "FAIL"),
                    check("http_health", "PASS"),
                ]
            }
        )
        self.assert_rule(data, "SVC-HTTP-01")

    def test_10_network_pass_and_http_fails(self):
        data = evidence(
            {
                "service": [
                    check("process", "PASS"),
                    check("listening_port", "PASS"),
                    check("http_health", "FAIL"),
                ]
            }
        )
        self.assert_rule(data, "SVC-HTTP-01")

    def test_11_http_skip_does_not_match(self):
        data = evidence(
            {
                "service": [
                    check("process", "PASS"),
                    check("listening_port", "PASS"),
                    check("http_health", "SKIP"),
                ]
            }
        )
        result = diagnose(data)
        self.assertIsNone(result["rule_id"])
        self.assertEqual(result["diagnosis_status"], "INSUFFICIENT_EVIDENCE")

    def test_12_reference_evidence_reports_hardware_boot_gaps(self):
        paths = sorted(REFERENCE_EVIDENCE_DIR.glob("*.json"))
        self.assertEqual(len(paths), 3)
        for path in paths:
            with self.subTest(path=path.name), path.open(encoding="utf-8") as source:
                result = diagnose(json.load(source))
                self.assertIsNone(result["rule_id"])
                self.assertEqual(result["diagnosis_status"], "INSUFFICIENT_EVIDENCE")
                gaps = {(gap["layer"], gap["check_name"]) for gap in result["evidence_gaps"]}
                self.assertIn(("hardware", "system_health"), gaps)
                self.assertIn(("hardware", "power_state"), gaps)
                self.assertIn(("boot", "post_status"), gaps)
                self.assertIn(("boot", "boot_or_os_access"), gaps)

    def test_13_cli_accepts_evidence_from_an_arbitrary_path(self):
        engine_path = REPOSITORY_ROOT / "automation" / "diagnosis" / "diagnosis_engine.py"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            input_path = temporary_path / "custom-input.json"
            output_directory = temporary_path / "custom-output"
            input_path.write_text(json.dumps(evidence()), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(engine_path),
                    str(input_path),
                    "--output-dir",
                    str(output_directory),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            output_path = output_directory / "custom-input.diagnosis.json"
            self.assertTrue(output_path.exists())
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["host"], "test-host")
            self.assertEqual(result["diagnosis_status"], "NO_ISSUE")

    def test_14_number_five_current_hardware_and_manual_boot_are_healthy(self):
        data = evidence(
            {
                "hardware": [
                    check("ilo_reachability", "PASS"),
                    check("power_state", "On"),
                    check("system_health", "OK", state="Enabled"),
                    check("memory_health", "OK"),
                    check("dimm_status", "GoodInUse"),
                    check("storage_health", "OK", state="Enabled"),
                    check("storage_controller", "OK", state="Enabled"),
                    check("logical_drive", "OK", state="Enabled", raid="0"),
                    check("physical_drive", "OK", state="Enabled"),
                ],
                "boot": [
                    check("post_status", "FinishedPost"),
                    check("boot_state", "OSLoginConfirmed", source="manual"),
                    check("ssh_reachability", "UNKNOWN"),
                ],
            }
        )
        result = diagnose(data)
        self.assertIsNone(result["rule_id"])
        self.assertEqual(result["diagnosis_status"], "NO_ISSUE")

    def test_15_current_storage_ok_and_historical_iml_error_do_not_match(self):
        data = evidence(
            {
                "hardware": [
                    check("system_health", "OK"),
                    check("power_state", "On"),
                    check("storage_health", "OK"),
                    check(
                        "storage_iml_event",
                        "CRITICAL",
                        created="2026-08-20T00:00:00Z",
                        message="1785-Slot 0 Drive Array Not Configured; POST Error 289",
                    ),
                ],
                "boot": [
                    check("post_status", "FinishedPost"),
                    check("boot_state", "OSLoginConfirmed", source="manual"),
                ],
            }
        )
        data["incident_started_at"] = "2026-08-25T00:00:00Z"
        result = diagnose(data)
        self.assertIsNone(result["rule_id"])
        self.assertEqual(result["diagnosis_status"], "NO_ISSUE")


if __name__ == "__main__":
    unittest.main()
