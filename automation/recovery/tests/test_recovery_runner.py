import json
import os
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from automation.recovery.recovery_runner import (
    RecoveryRunnerError,
    evaluate_verification,
    main,
    run_recovery,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PRODUCTION_FILES = (
    REPOSITORY_ROOT / "automation" / "recovery" / "recovery_runner.py",
    REPOSITORY_ROOT
    / "automation"
    / "ansible"
    / "roles"
    / "network_recovery"
    / "tasks"
    / "main.yml",
    REPOSITORY_ROOT
    / "automation"
    / "ansible"
    / "playbooks"
    / "incident_network_recovery.yml",
)
REQUIRED_CHECKS = [
    "nic_link",
    "ip_address",
    "gateway",
    "routes",
    "process",
    "listening_port",
]
OPTIONAL_CHECKS = ["http_health"]

DAY3_ACTION = (
    "Verify the gateway and required destination routes, then correct the routing configuration."
)


def diagnosis(**overrides):
    value = {
        "incident_id": "INC-001",
        "host": "dca-target01",
        "rule_id": "NET-ROUTE-01",
        "recommended_action": "network_recovery",
        "diagnosis_status": "MATCHED",
    }
    value.update(overrides)
    return value


def incident_result(**diagnosis_overrides):
    value = diagnosis(**diagnosis_overrides)
    value.pop("incident_id")
    value.pop("host")
    value["recommended_action"] = DAY3_ACTION
    return {
        "incident_id": "INC-001",
        "host": "dca-target01",
        "evidence": [],
        "diagnosis": value,
    }


def recovery_vars(**overrides):
    value = {
        "interface": "eno49",
        "gateway": "192.0.2.1",
        "routes": [{"destination": "198.51.100.0/24", "via": "192.0.2.1"}],
        "verification": {"required_checks": [*REQUIRED_CHECKS, *OPTIONAL_CHECKS]},
    }
    value.update(overrides)
    return value


def evidence(**results):
    defaults = {name: "PASS" for name in [*REQUIRED_CHECKS, *OPTIONAL_CHECKS]}
    defaults.update(results)
    return [
        {
            "layer": "service" if name in {"process", "listening_port", "http_health"} else "network",
            "check_name": name,
            "result": result,
            "detail": "Not configured" if name == "http_health" and result == "SKIP" else "",
        }
        for name, result in defaults.items()
    ]


def recovery_output():
    return {
        "before": {"routes": [{"dst": "198.51.100.0/24"}]},
        "after": {"routes": [{"dst": "198.51.100.0/24", "gateway": "192.0.2.1"}]},
    }


class RecoveryRunnerTests(unittest.TestCase):
    @patch("automation.recovery.recovery_runner.run_recovery_playbook")
    def test_01_net_route_maps_to_network_recovery_plan(self, mocked_playbook):
        result = run_recovery("INC-001", "dca-target01", incident_result(), recovery_vars())
        self.assertEqual(result["rule_id"], "NET-ROUTE-01")
        self.assertEqual(result["action"], "network_recovery")
        self.assertEqual(result["mode"], "PLAN_ONLY")
        self.assertEqual(result["result"], "PLANNED")
        mocked_playbook.assert_not_called()

    def test_02_recommended_action_mismatch_is_blocked(self):
        with self.assertRaisesRegex(RecoveryRunnerError, "recommended_action"):
            run_recovery(
                "INC-001",
                "dca-target01",
                diagnosis(recommended_action="restart_network"),
                recovery_vars(),
            )

    def test_03_incident_id_mismatch_is_blocked(self):
        with self.assertRaisesRegex(RecoveryRunnerError, "incident_id"):
            run_recovery("INC-001", "dca-target01", diagnosis(incident_id="INC-002"), recovery_vars())

    def test_04_host_mismatch_is_blocked(self):
        with self.assertRaisesRegex(RecoveryRunnerError, "host"):
            run_recovery("INC-001", "dca-target01", diagnosis(host="other-host"), recovery_vars())

    def test_05_missing_rule_is_blocked(self):
        with self.assertRaisesRegex(RecoveryRunnerError, "Only NET-ROUTE-01"):
            run_recovery("INC-001", "dca-target01", diagnosis(rule_id=None), recovery_vars())

    def test_06_insufficient_evidence_is_blocked(self):
        with self.assertRaisesRegex(RecoveryRunnerError, "not recoverable"):
            run_recovery(
                "INC-001",
                "dca-target01",
                diagnosis(rule_id=None, diagnosis_status="INSUFFICIENT_EVIDENCE"),
                recovery_vars(),
            )

    def test_07_other_layer_rules_are_blocked(self):
        for rule_id in ("SVC-HTTP-01", "HW-STORAGE-01", "BOOT-OS-01"):
            with self.subTest(rule_id=rule_id), self.assertRaises(RecoveryRunnerError):
                run_recovery("INC-001", "dca-target01", diagnosis(rule_id=rule_id), recovery_vars())

    def test_08_missing_required_recovery_vars_are_blocked(self):
        for key in ("interface", "gateway", "routes", "verification"):
            value = recovery_vars()
            value.pop(key)
            with self.subTest(key=key), self.assertRaises(RecoveryRunnerError):
                run_recovery("INC-001", "dca-target01", diagnosis(), value)

    def test_09_invalid_interface_ip_and_cidr_are_blocked(self):
        invalid_values = (
            recovery_vars(interface="eno49;down"),
            recovery_vars(gateway="192.0.2.1;id"),
            recovery_vars(routes=[{"destination": "198.51.100.7/24", "via": "192.0.2.1"}]),
            recovery_vars(routes=[{"destination": "198.51.100.0/24", "via": "not-an-ip"}]),
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(RecoveryRunnerError):
                run_recovery("INC-001", "dca-target01", diagnosis(), value)

    def test_10_commands_extra_keys_empty_and_duplicate_routes_are_blocked(self):
        values = (
            recovery_vars(command="ip route flush table main"),
            recovery_vars(routes=[]),
            recovery_vars(
                routes=[
                    {"destination": "198.51.100.0/24", "via": "192.0.2.1"},
                    {"destination": "198.51.100.0/24", "via": "192.0.2.2"},
                ]
            ),
            recovery_vars(
                routes=[
                    {
                        "destination": "198.51.100.0/24",
                        "via": "192.0.2.1",
                        "shell": "id",
                    }
                ]
            ),
        )
        for value in values:
            with self.subTest(value=value), self.assertRaises(RecoveryRunnerError):
                run_recovery("INC-001", "dca-target01", diagnosis(), value)

    def test_11_default_route_requires_both_safety_approvals(self):
        route = [{"destination": "0.0.0.0/0", "via": "192.0.2.1"}]
        for value in (
            recovery_vars(routes=route),
            recovery_vars(routes=route, allow_default_route_change=True),
        ):
            with self.subTest(value=value), self.assertRaises(RecoveryRunnerError):
                run_recovery("INC-001", "dca-target01", diagnosis(), value)

    def test_11a_all_network_checks_are_mandatory(self):
        for check_name in ("nic_link", "ip_address", "gateway", "routes"):
            value = recovery_vars()
            value["verification"]["required_checks"].remove(check_name)
            with self.subTest(check_name=check_name), self.assertRaisesRegex(
                RecoveryRunnerError, "mandatory network and SSH checks"
            ):
                run_recovery("INC-001", "dca-target01", diagnosis(), value)

    def test_11b_service_checks_are_mandatory(self):
        value = recovery_vars()
        value["verification"]["required_checks"] = [
            "nic_link",
            "ip_address",
            "gateway",
            "routes",
        ]
        with self.assertRaisesRegex(RecoveryRunnerError, "mandatory network and SSH checks"):
            run_recovery("INC-001", "dca-target01", diagnosis(), value)

    @patch("automation.recovery.recovery_runner.run_recovery_playbook")
    def test_12_execute_false_never_runs_ansible(self, mocked_playbook):
        run_recovery("INC-001", "dca-target01", diagnosis(), recovery_vars(), execute=False)
        mocked_playbook.assert_not_called()

    @patch("automation.recovery.recovery_runner.collect_verification", return_value=evidence())
    @patch("automation.recovery.recovery_runner.run_recovery_playbook", return_value=recovery_output())
    def test_13_execute_true_calls_only_allowed_playbook(self, mocked_playbook, _mocked_verify):
        result = run_recovery(
            "INC-001", "dca-target01", diagnosis(), recovery_vars(), execute=True
        )
        mocked_playbook.assert_called_once()
        self.assertEqual(result["mode"], "EXECUTE")
        self.assertEqual(result["verification_status"], "VERIFIED")
        self.assertEqual(
            set(result["verification"]),
            {"status", "required_checks", "optional_checks", "excluded_checks"},
        )

    @patch(
        "automation.recovery.recovery_runner.collect_verification",
        return_value=evidence(http_health="SKIP"),
    )
    @patch("automation.recovery.recovery_runner.run_recovery_playbook", return_value=recovery_output())
    def test_13a_execute_returns_unconfigured_http_as_excluded(
        self, _mocked_playbook, _mocked_verify
    ):
        result = run_recovery(
            "INC-001", "dca-target01", diagnosis(), recovery_vars(), execute=True
        )
        self.assertEqual(result["verification_status"], "VERIFIED")
        self.assertEqual(result["verification"]["optional_checks"], [])
        self.assertEqual(
            result["verification"]["excluded_checks"],
            [{"check_name": "http_health", "reason": "ENDPOINT_NOT_CONFIGURED"}],
        )

    def test_14_all_required_pass_is_verified(self):
        result = evaluate_verification(evidence(), REQUIRED_CHECKS)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(
            [item["check_name"] for item in result["required_checks"]], REQUIRED_CHECKS
        )
        self.assertEqual(result["optional_checks"][0]["check_name"], "http_health")
        self.assertEqual(result["excluded_checks"], [])

    def test_15_gateway_or_routes_fail_requires_escalation(self):
        for check_name in ("gateway", "routes"):
            with self.subTest(check_name=check_name):
                self.assertEqual(
                    evaluate_verification(evidence(**{check_name: "FAIL"}), REQUIRED_CHECKS)["status"],
                    "ESCALATION_REQUIRED",
                )

    def test_16_nic_or_ip_fail_requires_escalation(self):
        for check_name in ("nic_link", "ip_address"):
            with self.subTest(check_name=check_name):
                self.assertEqual(
                    evaluate_verification(evidence(**{check_name: "FAIL"}), REQUIRED_CHECKS)["status"],
                    "ESCALATION_REQUIRED",
                )

    def test_17_missing_unknown_or_skip_requires_escalation(self):
        missing = [item for item in evidence() if item["check_name"] != "routes"]
        cases = (missing, evidence(gateway="UNKNOWN"), evidence(process="SKIP"))
        for value in cases:
            with self.subTest(value=value):
                self.assertEqual(
                    evaluate_verification(value, REQUIRED_CHECKS)["status"],
                    "ESCALATION_REQUIRED",
                )

    def test_17b_unconfigured_http_skip_is_excluded_and_verified(self):
        result = evaluate_verification(evidence(http_health="SKIP"), REQUIRED_CHECKS)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["optional_checks"], [])
        self.assertEqual(
            result["excluded_checks"],
            [{"check_name": "http_health", "reason": "ENDPOINT_NOT_CONFIGURED"}],
        )

    def test_17c_active_http_failure_or_unknown_requires_escalation(self):
        for status in ("FAIL", "UNKNOWN"):
            with self.subTest(status=status):
                result = evaluate_verification(evidence(http_health=status), REQUIRED_CHECKS)
                self.assertEqual(result["status"], "ESCALATION_REQUIRED")
                self.assertEqual(result["optional_checks"][0]["results"], [status])

    def test_17d_http_skip_without_unconfigured_detail_requires_escalation(self):
        value = evidence(http_health="SKIP")
        value[-1]["detail"] = "probe disabled unexpectedly"
        result = evaluate_verification(value, REQUIRED_CHECKS)
        self.assertEqual(result["status"], "ESCALATION_REQUIRED")
        self.assertEqual(result["excluded_checks"], [])

    def test_17e_missing_active_check_requires_escalation(self):
        for check_name in (*REQUIRED_CHECKS, *OPTIONAL_CHECKS):
            value = [item for item in evidence() if item["check_name"] != check_name]
            with self.subTest(check_name=check_name):
                result = evaluate_verification(value, REQUIRED_CHECKS)
                self.assertEqual(result["status"], "ESCALATION_REQUIRED")

    def test_17a_day3_incident_envelope_identity_is_enforced(self):
        for key, value in (("incident_id", "INC-OTHER"), ("host", "other-host")):
            payload = incident_result()
            payload[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RecoveryRunnerError, key):
                run_recovery("INC-001", "dca-target01", payload, recovery_vars())

    def test_18_unrelated_hardware_gap_does_not_affect_network_verify(self):
        value = evidence()
        value.append(
            {"layer": "hardware", "check_name": "storage_health", "result": "UNKNOWN"}
        )
        self.assertEqual(evaluate_verification(value, REQUIRED_CHECKS)["status"], "VERIFIED")

    def test_19_return_value_is_json_serializable(self):
        result = run_recovery("INC-001", "dca-target01", diagnosis(), recovery_vars())
        json.dumps(result)

    def test_20_import_has_no_side_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(REPOSITORY_ROOT)
            completed = subprocess.run(
                [sys.executable, "-B", "-c", "import automation.recovery.recovery_runner"],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout, "")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_21_no_credentials_or_shell_module_in_production_code(self):
        content = "\n".join(path.read_text(encoding="utf-8") for path in PRODUCTION_FILES)
        for forbidden in (
            "ansible_password",
            "--ask-pass",
            "ansible.builtin.shell",
            "shell:",
            "api_token",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)

    @patch("automation.recovery.recovery_runner.run_recovery")
    def test_22_cli_returns_single_json_and_uses_plan_by_default(self, mocked_runner):
        mocked_runner.return_value = {
            "incident_id": "INC-001",
            "host": "dca-target01",
            "result": "PLANNED",
        }
        with tempfile.TemporaryDirectory() as directory:
            diagnosis_path = Path(directory) / "diagnosis.json"
            vars_path = Path(directory) / "vars.json"
            diagnosis_path.write_text(json.dumps(diagnosis()), encoding="utf-8")
            vars_path.write_text(json.dumps(recovery_vars()), encoding="utf-8")
            stdout = StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "recovery_runner.py",
                    "--incident-id",
                    "INC-001",
                    "--host",
                    "dca-target01",
                    "--diagnosis-json",
                    str(diagnosis_path),
                    "--recovery-vars",
                    str(vars_path),
                ],
            ), patch("sys.stdout", stdout):
                exit_code = main()
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), mocked_runner.return_value)
        self.assertFalse(mocked_runner.call_args.kwargs["execute"])

    def test_23_direct_script_cli_is_importable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(REPOSITORY_ROOT / "automation" / "recovery" / "recovery_runner.py"),
                "--help",
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--diagnosis-json", completed.stdout)


if __name__ == "__main__":
    unittest.main()
