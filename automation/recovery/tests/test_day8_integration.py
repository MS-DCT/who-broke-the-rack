import inspect
import json
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from automation.recovery.escalation_engine import LEVELS, run_escalation
from automation.recovery.recovery_runner import RecoveryRunnerError, run_recovery
from automation.recovery.standard_build_runner import run_standard_build
from automation.recovery.workflow_runner import WorkflowError, run_workflow


def incident(rule="SVC-HTTP-01", host="dca-target02"):
    action = "service_recovery" if rule == "SVC-HTTP-01" else "network_recovery"
    return {
        "incident_id": "INC-DAY8",
        "host": host,
        "evidence": [],
        "diagnosis": {
            "diagnosis_status": "MATCHED",
            "rule_id": rule,
            "recommended_action": action,
        },
    }


class Day8IntegrationTests(unittest.TestCase):
    def test_public_signatures_remain_explicit(self):
        self.assertEqual(
            list(inspect.signature(run_recovery).parameters),
            ["incident_id", "host", "diagnosis", "recovery_vars", "execute"],
        )
        self.assertEqual(
            list(inspect.signature(run_escalation).parameters),
            [
                "incident_id",
                "failed_host",
                "rule_id",
                "current_level",
                "attempted_levels",
                "retry_count",
                "execution_state",
                "adapters",
                "reason",
            ],
        )
        self.assertEqual(
            list(inspect.signature(run_standard_build).parameters),
            ["host", "execute", "approved_profile"],
        )
        self.assertEqual(list(inspect.signature(run_workflow).parameters)[:3], ["incident_id", "failed_host", "recovery_vars"])

    def test_plan_only_defaults_are_json_serializable(self):
        recovery = run_recovery(
            "INC-DAY8",
            "dca-target02",
            incident()["diagnosis"],
            {
                "profile": "dca_target02_nginx",
                "config_content": None,
                "http_enabled": True,
            },
        )
        standard_build = run_standard_build()
        self.assertEqual(recovery["mode"], "PLAN_ONLY")
        self.assertEqual(standard_build["mode"], "PLAN_ONLY")
        json.dumps(recovery)
        json.dumps(standard_build)

    def test_unsupported_rule_and_missing_diagnosis_are_distinct(self):
        with self.assertRaisesRegex(RecoveryRunnerError, "Unsupported recovery rule"):
            run_recovery("INC-DAY8", "dca-target02", {"rule_id": "HW-OTHER"}, {})
        with self.assertRaisesRegex(WorkflowError, "recoverable diagnosis"):
            run_workflow("INC-DAY8", "dca-target02", {}, incident_result={"diagnosis": {}})

    def test_timeout_and_retry_are_bounded(self):
        calls = Mock(side_effect=lambda _payload: (time.sleep(0.02), {"status": "SUCCESS"})[1])
        with patch.dict(LEVELS["L3"], {"timeout_seconds": 0.001}):
            timed_out = run_escalation(
                "INC-DAY8-TIMEOUT",
                "dca-target02",
                "SVC-HTTP-01",
                current_level="L3",
                adapters={"NODE_ISOLATION": calls},
            )
        self.assertEqual(timed_out["status"], "TIMEOUT")
        self.assertEqual(timed_out["retry_count"], 0)
        self.assertEqual(calls.call_count, 1)

        retrying = Mock(return_value={"status": "ERROR", "error": "mock failure"})
        retried = run_escalation(
            "INC-DAY8-RETRY",
            "dca-target02",
            "SVC-HTTP-01",
            current_level="L1",
            adapters={"SERVICE_REPAIR": retrying},
        )
        self.assertEqual(retrying.call_count, 2)
        self.assertEqual(retried["retry_count"], 1)
        self.assertEqual(retried["next_level"], "L2")

    def test_manual_required_and_timeline_contract(self):
        result = run_escalation(
            "INC-DAY8-MANUAL",
            "dca-target02",
            "SVC-HTTP-01",
            current_level="L3",
        )
        self.assertEqual(result["status"], "MANUAL_REQUIRED")
        event = result["timeline_events"][0]
        self.assertEqual(
            set(event),
            {
                "incident_id",
                "timestamp",
                "level",
                "action",
                "target_host",
                "status",
                "result",
                "detail",
                "duration_ms",
            },
        )
        json.dumps(result)

    def test_resume_state_prevents_duplicate_software_execution(self):
        state = {}
        recovery = Mock(return_value={"verification_status": "VERIFIED", "mode": "EXECUTE"})
        first = run_workflow(
            "INC-DAY8",
            "dca-target02",
            {},
            execute=True,
            incident_result=incident(),
            execution_state=state,
            recovery_runner=recovery,
        )
        second = run_workflow(
            "INC-DAY8",
            "dca-target02",
            {},
            execute=True,
            incident_result=incident(),
            execution_state=state,
            recovery_runner=recovery,
        )
        self.assertEqual(first["status"], "VERIFIED")
        self.assertEqual(second["status"], "VERIFIED")
        self.assertEqual(recovery.call_count, 1)
        json.dumps(second)

    def test_workflow_layer_does_not_import_or_write_backend_database(self):
        content = (Path(__file__).resolve().parents[1] / "workflow_runner.py").read_text(encoding="utf-8")
        self.assertNotIn("backend.database", content)
        self.assertNotIn("from backend", content)
        self.assertNotIn("import backend", content)


if __name__ == "__main__":
    unittest.main()
