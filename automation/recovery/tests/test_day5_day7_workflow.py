import json
import unittest
from unittest.mock import Mock

from automation.recovery.escalation_engine import run_escalation
from automation.recovery.recovery_runner import RecoveryRunnerError, run_recovery
from automation.recovery.standard_build_runner import CHECKS, evaluate_standard_build, run_standard_build
from automation.recovery.workflow_runner import run_workflow


def incident(rule="SVC-HTTP-01", host="dca-target02"):
    action = "service_recovery" if rule == "SVC-HTTP-01" else "network_recovery"
    return {"incident_id": "INC-DAY7", "host": host, "evidence": [], "diagnosis": {"rule_id": rule, "recommended_action": action, "diagnosis_status": "MATCHED"}}


def nginx_vars(**overrides):
    value = {"profile": "dca_target02_nginx", "config_content": None, "http_enabled": True}
    value.update(overrides)
    return value


class Day5Day7Tests(unittest.TestCase):
    def test_nginx_plan_is_fixed_and_does_not_restore_unsupplied_config(self):
        result = run_recovery("INC-DAY7", "dca-target02", incident(), nginx_vars())
        self.assertEqual(result["after"]["service_name"], "nginx.service")
        self.assertEqual(result["after"]["validation_argv"], ["/usr/sbin/nginx", "-t"])
        self.assertFalse(result["after"]["config_restore_requested"])

    def test_nginx_profile_rejects_wrong_host_and_extra_commands(self):
        with self.assertRaises(RecoveryRunnerError):
            run_recovery("INC-DAY7", "dca-target01", incident(host="dca-target01"), nginx_vars())
        with self.assertRaises(RecoveryRunnerError):
            run_recovery("INC-DAY7", "dca-target02", incident(), nginx_vars(validation_argv=["/bin/sh"]))

    def test_escalation_is_bounded_json_and_duplicate_safe(self):
        state = {}
        first = run_escalation("INC-DAY7", "dca-target02", "SVC-HTTP-01", current_level="L3", execution_state=state)
        second = run_escalation("INC-DAY7", "dca-target02", "SVC-HTTP-01", current_level="L3", execution_state=state)
        self.assertEqual(first["status"], "MANUAL_REQUIRED")
        self.assertEqual(second["status"], "DUPLICATE_BLOCKED")
        json.dumps(first)

    def test_standard_build_is_plan_only_and_all_pass_can_verify(self):
        self.assertEqual(run_standard_build()["status"], "PLANNED")
        checks = evaluate_standard_build({name: "PASS" for name in CHECKS})
        self.assertEqual(checks["overall_status"], "PASS")

    def test_service_and_network_software_recovery_can_verify(self):
        for rule, host in (("SVC-HTTP-01", "dca-target02"), ("NET-ROUTE-01", "dca-target01")):
            recovery = Mock(return_value={"verification_status": "VERIFIED", "mode": "EXECUTE"})
            result = run_workflow("INC-DAY7", host, {}, execute=True, incident_result=incident(rule, host), recovery_runner=recovery)
            self.assertEqual(result["status"], "VERIFIED")
            recovery.assert_called_once()

    def test_failed_service_requests_l2_then_manual_node_isolation(self):
        recovery = Mock(return_value={"verification_status": "ESCALATION_REQUIRED", "mode": "EXECUTE"})
        result = run_workflow("INC-DAY7", "dca-target02", nginx_vars(), execute=True, incident_result=incident(), recovery_runner=recovery)
        self.assertEqual(result["status"], "MANUAL_REQUIRED")
        self.assertEqual(result["attempted_levels"], ["L1", "L2", "L3"])
        self.assertEqual(result["next_action"], "SPARE_ACTIVATION")

    def test_physical_callbacks_reach_standard_build_health_validation(self):
        recovery = Mock(return_value={"verification_status": "ESCALATION_REQUIRED", "mode": "EXECUTE"})
        adapters = {
            "NODE_ISOLATION": lambda payload: {"status": "SUCCESS", "payload": payload},
            "SPARE_ACTIVATION": lambda payload: {"status": "SUCCESS", "payload": payload},
            "PXE_REBUILD": lambda payload: {"status": "VERIFIED", "payload": payload},
        }
        build = Mock(return_value={"status": "VERIFIED"})
        result = run_workflow("INC-DAY7", "dca-target01", {}, execute=True, incident_result=incident("NET-ROUTE-01", "dca-target01"), recovery_runner=recovery, adapters=adapters, standard_build_runner=build)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["attempted_levels"], ["L2", "L3", "L4", "L5"])
        build.assert_called_once_with("dca-spare01", execute=False)


if __name__ == "__main__":
    unittest.main()
