import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from automation.recovery.recovery_runner import (
    RecoveryRunnerError,
    main,
    run_recovery,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROLE = (
    REPOSITORY_ROOT
    / "automation"
    / "ansible"
    / "roles"
    / "service_recovery"
    / "tasks"
    / "main.yml"
)


def service_diagnosis(**overrides):
    value = {
        "incident_id": "INC-SVC-001",
        "host": "dca-target02",
        "rule_id": "SVC-HTTP-01",
        "recommended_action": "service_recovery",
        "diagnosis_status": "MATCHED",
    }
    value.update(overrides)
    return value


def service_vars(**overrides):
    value = {
        "profile": "day5_mock_http",
        "config_content": "listen=18080\nhealth_path=/health\n",
        "http_enabled": True,
    }
    value.update(overrides)
    return value


def verification_evidence(**overrides):
    results = {
        "nic_link": "PASS",
        "ip_address": "PASS",
        "gateway": "PASS",
        "routes": "PASS",
        "process": "PASS",
        "listening_port": "PASS",
        "http_health": "PASS",
    }
    results.update(overrides)
    return [
        {
            "layer": (
                "service"
                if name in {"process", "listening_port", "http_health"}
                else "network"
            ),
            "check_name": name,
            "result": result,
            "detail": "mock evidence",
        }
        for name, result in results.items()
    ]


def service_recovery_output():
    return {
        "changed": True,
        "before": {"config_validation_rc": 1},
        "after": {
            "config_validation": "PASS",
            "process": "PASS",
            "listening_port": "PASS",
            "http_health": "PASS",
        },
    }


class ServiceRecoveryTests(unittest.TestCase):
    @patch("automation.recovery.recovery_runner.run_recovery_playbook")
    @patch("automation.recovery.recovery_runner.run_service_recovery_playbook")
    def test_rule_dispatch_selects_service_role(self, mocked_service, mocked_network):
        result = run_recovery(
            "INC-SVC-001", "dca-target02", service_diagnosis(), service_vars()
        )
        self.assertEqual(result["rule_id"], "SVC-HTTP-01")
        self.assertEqual(result["action"], "service_recovery")
        self.assertEqual(result["mode"], "PLAN_ONLY")
        mocked_service.assert_not_called()
        mocked_network.assert_not_called()

    def test_unsupported_rule_is_rejected(self):
        with self.assertRaisesRegex(RecoveryRunnerError, "Unsupported recovery rule"):
            run_recovery(
                "INC-SVC-001",
                "dca-target02",
                service_diagnosis(rule_id="BOOT-OS-01"),
                service_vars(),
            )

    @patch("automation.recovery.recovery_runner.run_service_recovery_playbook")
    def test_plan_only_never_changes_service(self, mocked_service):
        result = run_recovery(
            "INC-SVC-001", "dca-target02", service_diagnosis(), service_vars()
        )
        self.assertEqual(result["result"], "PLANNED")
        self.assertEqual(result["verification_status"], "NOT_RUN")
        self.assertTrue(result["after"]["config_restore_requested"])
        mocked_service.assert_not_called()

    @patch(
        "automation.recovery.recovery_runner.collect_verification",
        return_value=verification_evidence(),
    )
    @patch(
        "automation.recovery.recovery_runner.run_service_recovery_playbook",
        return_value=service_recovery_output(),
    )
    def test_service_restart_config_restore_and_health_success(
        self, mocked_service, _mocked_verification
    ):
        result = run_recovery(
            "INC-SVC-001",
            "dca-target02",
            service_diagnosis(),
            service_vars(),
            execute=True,
        )
        mocked_service.assert_called_once()
        passed = {
            item["check_name"]
            for item in result["verification"]["required_checks"]
            if item["results"] == ["PASS"]
        }
        self.assertTrue({"process", "listening_port", "http_health"} <= passed)
        self.assertEqual(result["verification_status"], "VERIFIED")
        self.assertEqual(result["result"], "SUCCESS")

    def test_arbitrary_package_path_service_and_validation_command_are_blocked(self):
        for key, value in (
            ("service_name", "sshd.service"),
            ("package_name", "openssh-server"),
            ("config_path", "/etc/ssh/sshd_config"),
            ("validation_argv", ["/bin/sh", "-c", "id"]),
        ):
            with self.subTest(key=key), self.assertRaises(RecoveryRunnerError):
                run_recovery(
                    "INC-SVC-001",
                    "dca-target02",
                    service_diagnosis(),
                    service_vars(**{key: value}),
                )

    def test_unknown_profile_and_invalid_config_are_blocked(self):
        values = (
            service_vars(profile="unknown"),
            service_vars(config_content={"not": "text"}),
            service_vars(config_content="x" * 65537),
        )
        for value in values:
            with self.subTest(value_type=type(value.get("config_content"))):
                with self.assertRaises(RecoveryRunnerError):
                    run_recovery(
                        "INC-SVC-001",
                        "dca-target02",
                        service_diagnosis(),
                        value,
                    )

    @patch(
        "automation.recovery.recovery_runner.run_service_recovery_playbook",
        side_effect=RecoveryRunnerError("package or config validation failed"),
    )
    def test_package_or_config_validation_failure_stops_recovery(self, _mocked_service):
        with self.assertRaisesRegex(RecoveryRunnerError, "validation failed"):
            run_recovery(
                "INC-SVC-001",
                "dca-target02",
                service_diagnosis(),
                service_vars(),
                execute=True,
            )

    def test_role_uses_safe_idempotent_modules_and_validation(self):
        content = SERVICE_ROLE.read_text(encoding="utf-8")
        self.assertNotIn("ansible.builtin.shell", content)
        self.assertIn("'sshd.service'", content)
        self.assertIn("ansible.builtin.package_facts", content)
        self.assertIn("Validate candidate config before deployment", content)
        self.assertIn("Validate deployed config after recovery", content)
        self.assertIn("Restart service only when config or active health requires it", content)
        self.assertIn("ansible.builtin.systemd_service", content)

    @patch(
        "automation.recovery.recovery_runner.run_service_recovery_playbook",
        return_value=service_recovery_output(),
    )
    def test_http_skip_unknown_fail_or_missing_requires_escalation(self, _mocked_service):
        cases = {
            "SKIP": verification_evidence(http_health="SKIP"),
            "UNKNOWN": verification_evidence(http_health="UNKNOWN"),
            "FAIL": verification_evidence(http_health="FAIL"),
            "MISSING": [
                item
                for item in verification_evidence()
                if item["check_name"] != "http_health"
            ],
        }
        for label, evidence in cases.items():
            with self.subTest(label=label), patch(
                "automation.recovery.recovery_runner.collect_verification",
                return_value=evidence,
            ):
                result = run_recovery(
                    "INC-SVC-001",
                    "dca-target02",
                    service_diagnosis(),
                    service_vars(),
                    execute=True,
                )
                self.assertEqual(result["verification_status"], "ESCALATION_REQUIRED")
                self.assertEqual(result["result"], "FAILED")

    @patch("automation.recovery.recovery_runner.run_recovery")
    def test_cli_returns_two_for_escalation(self, mocked_runner):
        mocked_runner.return_value = {
            "incident_id": "INC-SVC-001",
            "host": "dca-target02",
            "verification_status": "ESCALATION_REQUIRED",
        }
        with tempfile.TemporaryDirectory() as directory:
            diagnosis_path = Path(directory) / "diagnosis.json"
            vars_path = Path(directory) / "vars.json"
            diagnosis_path.write_text(json.dumps(service_diagnosis()), encoding="utf-8")
            vars_path.write_text(json.dumps(service_vars()), encoding="utf-8")
            stdout = StringIO()
            with patch(
                "sys.argv",
                [
                    "recovery_runner.py",
                    "--incident-id",
                    "INC-SVC-001",
                    "--host",
                    "dca-target02",
                    "--diagnosis-json",
                    str(diagnosis_path),
                    "--recovery-vars",
                    str(vars_path),
                    "--execute",
                ],
            ), patch("sys.stdout", stdout):
                self.assertEqual(main(), 2)


if __name__ == "__main__":
    unittest.main()
