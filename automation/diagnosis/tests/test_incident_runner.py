import json
import inspect
import os
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from automation.diagnosis.diagnosis_engine import diagnose
from automation.diagnosis.incident_runner import (
    IncidentRunnerError,
    flatten_evidence,
    load_and_merge_hardware,
    main,
    normalize_hardware_evidence,
    run_ansible_collection,
    run_incident,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DIAGNOSIS_KEYS = {
    "rule_id",
    "root_cause",
    "matched_evidence",
    "recommended_action",
    "severity",
}
EVIDENCE_KEYS = {
    "incident_id",
    "timestamp",
    "host",
    "layer",
    "source",
    "check_name",
    "result",
    "severity",
    "detail",
    "value",
}


def collected_evidence(incident_id, host, incident_started_at):
    return {
        "incident_id": incident_id,
        "incident_started_at": incident_started_at,
        "host": host,
        "ansible_host": "192.0.2.10",
        "generated_at": "2026-08-25T00:01:00Z",
        "results": [
            {
                "category": "network",
                "checks": [
                    {"name": "nic_link", "status": "PASS"},
                    {"name": "ip_address", "status": "PASS"},
                    {"name": "gateway", "status": "PASS"},
                    {"name": "routes", "status": "PASS"},
                ],
            },
            {"category": "os", "checks": []},
            {
                "category": "service",
                "checks": [
                    {"name": "process", "status": "PASS"},
                    {"name": "listening_port", "status": "PASS"},
                    {"name": "http_health", "status": "PASS"},
                ],
            },
        ],
    }


def write_mock_collection(**kwargs):
    data = collected_evidence(
        kwargs["incident_id"], kwargs["host"], kwargs["incident_started_at"]
    )
    (kwargs["output_dir"] / f"{kwargs['host']}.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


def number_five_hardware(host):
    return {
        "host": host,
        "results": [
            {
                "category": "hardware",
                "checks": [
                    {"name": "ilo_reachability", "status": "PASS"},
                    {"name": "power_state", "status": "On"},
                    {"name": "system_health", "status": "OK", "state": "Enabled"},
                    {"name": "memory_health", "status": "OK"},
                    {"name": "dimm_status", "status": "GoodInUse"},
                    {"name": "storage_health", "status": "OK"},
                    {"name": "storage_controller", "status": "OK"},
                    {"name": "logical_drive", "status": "OK", "raid": "0"},
                    {"name": "physical_drive", "status": "OK"},
                ],
            },
            {
                "category": "boot",
                "checks": [
                    {"name": "post_status", "status": "FinishedPost"},
                    {
                        "name": "boot_state",
                        "status": "OSLoginConfirmed",
                        "source": "manual",
                    },
                    {"name": "ssh_reachability", "status": "UNKNOWN"},
                ],
            },
        ],
    }


def common_hardware(incident_id="INC-COMMON", host="dca-target01"):
    return {
        "incident_id": incident_id,
        "server_id": "server-205",
        "host": host,
        "timestamp": "2026-08-27T00:00:00Z",
        "category": "hardware",
        "source": "redfish",
        "evidence": {
            "ilo_reachability": {
                "result": "PASS",
                "value": "reachable",
                "detail": "Redfish API 정상 응답",
                "source": "/redfish/v1/",
            },
            "power_state": {"result": "PASS", "value": "On"},
            "system_health": {"result": "PASS", "value": "OK"},
            "storage_health": {"result": "PASS", "value": "OK"},
            "post_state": {"result": "PASS", "value": "FinishedPost"},
            "boot_state": {"result": "PASS", "value": "OSLoginConfirmed"},
        },
        "iml_events": [],
    }


class IncidentRunnerTests(unittest.TestCase):
    def test_common_hardware_dict_is_normalized_and_merged(self):
        merged = load_and_merge_hardware(
            collected_evidence("INC-COMMON", "dca-target01", "2026-08-27T00:00:00Z"),
            common_hardware(),
            "dca-target01",
        )
        categories = {item["category"]: item["checks"] for item in merged["results"]}
        self.assertIn("hardware", categories)
        self.assertIn("boot", categories)
        self.assertIn("post_state", {item["name"] for item in categories["boot"]})

    def test_common_hardware_json_path_is_normalized_and_merged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hardware.json"
            path.write_text(json.dumps(common_hardware()), encoding="utf-8")
            merged = load_and_merge_hardware(
                collected_evidence(
                    "INC-COMMON", "dca-target01", "2026-08-27T00:00:00Z"
                ),
                path,
                "dca-target01",
            )
        self.assertEqual(merged["results"][0]["category"], "hardware")

    def test_legacy_results_checks_hardware_remains_supported(self):
        merged = load_and_merge_hardware(
            collected_evidence("INC-LEGACY", "dca-target01", None),
            number_five_hardware("dca-target01"),
            "dca-target01",
        )
        self.assertEqual(merged["results"][0]["checks"][0]["name"], "ilo_reachability")

    def test_common_hardware_rejects_incident_id_mismatch(self):
        with self.assertRaisesRegex(IncidentRunnerError, "incident_id"):
            load_and_merge_hardware(
                collected_evidence("INC-EXPECTED", "dca-target01", None),
                common_hardware(incident_id="INC-DIFFERENT"),
                "dca-target01",
            )

    def test_common_hardware_rejects_host_mismatch(self):
        with self.assertRaises(IncidentRunnerError):
            load_and_merge_hardware(
                collected_evidence("INC-COMMON", "dca-target01", None),
                common_hardware(host="different-host"),
                "dca-target01",
            )

    def test_common_hardware_rejects_non_object_evidence(self):
        hardware = common_hardware()
        hardware["evidence"] = []
        with self.assertRaisesRegex(IncidentRunnerError, "must be an object"):
            normalize_hardware_evidence(
                hardware, incident_id="INC-COMMON", host="dca-target01"
            )

    def test_common_post_state_finished_post_is_read_by_boot_rule(self):
        hardware = common_hardware()
        hardware["evidence"]["boot_state"] = {"result": "FAIL", "value": "failed"}
        merged = load_and_merge_hardware(
            collected_evidence("INC-COMMON", "dca-target01", "2026-08-27T00:00:00Z"),
            hardware,
            "dca-target01",
        )
        self.assertEqual(diagnose(merged)["rule_id"], "BOOT-OS-01")

    def test_historical_storage_iml_warning_is_not_incident_related(self):
        hardware = common_hardware()
        hardware["evidence"]["storage_health"]["result"] = "FAIL"
        hardware["iml_events"] = [{
            "message": "old storage warning",
            "severity": "Warning",
            "created": "2026-08-20T00:00:00Z",
            "subsystem": "storage",
        }]
        merged = load_and_merge_hardware(
            collected_evidence("INC-COMMON", "dca-target01", "2026-08-27T00:00:00Z"),
            hardware,
            "dca-target01",
        )
        self.assertIsNone(diagnose(merged)["rule_id"])

    def test_current_storage_iml_event_is_processed_separately(self):
        hardware = common_hardware()
        hardware["evidence"]["storage_health"]["result"] = "FAIL"
        hardware["iml_events"] = [{
            "message": "current storage warning",
            "severity": "Warning",
            "created": "2026-08-27T00:01:00Z",
            "subsystem": "storage",
        }]
        merged = load_and_merge_hardware(
            collected_evidence("INC-COMMON", "dca-target01", "2026-08-27T00:00:00Z"),
            hardware,
            "dca-target01",
        )
        iml_check = next(
            check
            for category in merged["results"]
            for check in category["checks"]
            if check["name"] == "iml_event"
        )
        self.assertEqual(
            {
                key: iml_check[key]
                for key in ("message", "severity", "created", "subsystem")
            },
            {
                "message": "current storage warning",
                "severity": "Warning",
                "created": "2026-08-27T00:01:00Z",
                "subsystem": "storage",
            },
        )
        diagnosis = diagnose(merged)
        self.assertEqual(diagnosis["rule_id"], "HW-STORAGE-01")
        self.assertIn(
            {"layer": "hardware", "check_name": "iml_event", "result": "WARN"},
            diagnosis["matched_evidence"],
        )

    def test_common_hardware_flatten_preserves_detail_source_and_timestamp(self):
        merged = load_and_merge_hardware(
            collected_evidence("INC-COMMON", "dca-target01", "2026-08-27T00:00:00Z"),
            common_hardware(),
            "dca-target01",
        )
        flattened = flatten_evidence(merged)
        ilo = next(item for item in flattened if item["check_name"] == "ilo_reachability")
        power = next(item for item in flattened if item["check_name"] == "power_state")
        self.assertEqual(ilo["detail"], "Redfish API 정상 응답")
        self.assertEqual(ilo["source"], "/redfish/v1/")
        self.assertEqual(ilo["timestamp"], "2026-08-27T00:00:00Z")
        self.assertEqual(power["source"], "redfish")

    def test_flat_evidence_normalizes_names_and_accepts_legacy_details(self):
        data = {
            "incident_id": "INC-FLAT",
            "host": "dca-target01",
            "generated_at": "2026-08-25T00:00:00Z",
            "results": [
                {
                    "category": "Hardware",
                    "checks": [
                        {
                            "name": "SystemHealth",
                            "status": "OK",
                            "value": "OK",
                            "details": "Health=OK, State=Enabled",
                            "source": "/redfish/v1/Systems/1",
                        }
                    ],
                }
            ],
        }

        result = flatten_evidence(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["layer"], "hardware")
        self.assertEqual(result[0]["check_name"], "system_health")
        self.assertEqual(result[0]["result"], "PASS")
        self.assertEqual(result[0]["detail"], "Health=OK, State=Enabled")
        self.assertNotIn("details", result[0])

    def test_public_function_signature(self):
        parameters = inspect.signature(run_incident).parameters
        self.assertEqual(list(parameters), [
            "incident_id",
            "host",
            "incident_started_at",
            "hardware_evidence",
        ])
        self.assertEqual(parameters["incident_id"].kind, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        self.assertEqual(parameters["host"].kind, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        self.assertEqual(parameters["incident_started_at"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(parameters["hardware_evidence"].kind, inspect.Parameter.KEYWORD_ONLY)

    @patch(
        "automation.diagnosis.incident_runner.run_ansible_collection",
        side_effect=write_mock_collection,
    )
    def test_c_two_argument_call_returns_fixed_json_contract(self, mocked_collection):
        temporary_paths = []

        def capture_path(**kwargs):
            temporary_paths.append(kwargs["output_dir"])
            write_mock_collection(**kwargs)

        mocked_collection.side_effect = capture_path
        result = run_incident("INC-001", "dca-target01")

        self.assertEqual(set(result), {"incident_id", "host", "evidence", "diagnosis"})
        self.assertEqual(result["incident_id"], "INC-001")
        self.assertEqual(result["host"], "dca-target01")
        self.assertIsInstance(result["evidence"], list)
        self.assertTrue(result["evidence"])
        self.assertTrue(all(set(item) == EVIDENCE_KEYS for item in result["evidence"]))
        self.assertTrue(DIAGNOSIS_KEYS <= result["diagnosis"].keys())
        self.assertEqual(result["diagnosis"]["diagnosis_status"], "INSUFFICIENT_EVIDENCE")
        json.dumps(result)
        self.assertFalse(temporary_paths[0].exists())

    @patch(
        "automation.diagnosis.incident_runner.run_ansible_collection",
        side_effect=write_mock_collection,
    )
    def test_runner_merges_host_hardware_and_preserves_manual_source(self, _mock):
        with tempfile.TemporaryDirectory() as directory:
            hardware_path = Path(directory) / "hardware.json"
            hardware_path.write_text(
                json.dumps(number_five_hardware("dca-target01")), encoding="utf-8"
            )
            result = run_incident(
                "INC-002",
                "dca-target01",
                hardware_evidence=hardware_path,
            )

        boot_state = next(
            item
            for item in result["evidence"]
            if item["layer"] == "boot" and item["check_name"] == "boot_state"
        )
        self.assertEqual(boot_state["source"], "manual")
        self.assertEqual(result["diagnosis"]["diagnosis_status"], "NO_ISSUE")

    @patch(
        "automation.diagnosis.incident_runner.run_ansible_collection",
        side_effect=write_mock_collection,
    )
    def test_missing_incident_start_does_not_correlate_iml_event(self, _mock):
        hardware = number_five_hardware("dca-target01")
        hardware["results"][0]["checks"].extend(
            [
                {"name": "storage_health", "status": "FAIL"},
                {
                    "name": "storage_iml_event",
                    "severity": "CRITICAL",
                    "created": "2099-01-01T00:00:00Z",
                },
            ]
        )
        result = run_incident("INC-NO-START", "dca-target01", hardware_evidence=hardware)
        self.assertIsNone(result["diagnosis"]["rule_id"])

    @patch("automation.diagnosis.incident_runner.run_incident")
    def test_cli_delegates_to_same_run_incident_function(self, mocked_runner):
        mocked_runner.return_value = {
            "incident_id": "INC-CLI",
            "host": "dca-target02",
            "evidence": [],
            "diagnosis": {
                "rule_id": None,
                "root_cause": "Insufficient evidence",
                "matched_evidence": [],
                "recommended_action": "Collect evidence",
                "severity": "UNKNOWN",
            },
        }
        stdout = StringIO()
        with patch.object(
            sys,
            "argv",
            [
                "incident_runner.py",
                "--incident-id",
                "INC-CLI",
                "--host",
                "dca-target02",
                "--incident-started-at",
                "2026-08-25T00:00:00Z",
            ],
        ), patch("sys.stdout", stdout):
            exit_code = main()

        self.assertEqual(exit_code, 0)
        mocked_runner.assert_called_once_with(
            "INC-CLI",
            "dca-target02",
            incident_started_at="2026-08-25T00:00:00Z",
            hardware_evidence=None,
        )
        self.assertEqual(json.loads(stdout.getvalue()), mocked_runner.return_value)

    def test_module_import_has_no_execution_side_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(REPOSITORY_ROOT)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    "import automation.diagnosis.incident_runner",
                ],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout, "")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_hardware_merge_rejects_a_different_host(self):
        with tempfile.TemporaryDirectory() as directory:
            hardware_path = Path(directory) / "hardware.json"
            hardware_path.write_text(
                json.dumps(number_five_hardware("different-host")), encoding="utf-8"
            )
            with self.assertRaises(IncidentRunnerError):
                load_and_merge_hardware(
                    collected_evidence("INC-003", "dca-target01", "2026-08-25T00:00:00Z"),
                    hardware_path,
                    "dca-target01",
                )

    @patch("automation.diagnosis.incident_runner.subprocess.run")
    def test_ansible_command_uses_limit_and_no_password_flag(self, mocked_run):
        mocked_run.return_value = subprocess.CompletedProcess([], 0, "", "")
        run_ansible_collection(
            incident_id="INC-004",
            incident_started_at="2026-08-25T00:00:00Z",
            host="dca-target01",
            output_dir=Path("/tmp/incident-output"),
            inventory=Path("inventory.ini"),
            playbook=Path("incident_diagnostic.yml"),
            ansible_playbook="ansible-playbook",
        )
        command = mocked_run.call_args.args[0]
        self.assertEqual(command[command.index("--limit") + 1], "dca-target01")
        self.assertNotIn("-k", command)
        self.assertNotIn("--ask-pass", command)


if __name__ == "__main__":
    unittest.main()
