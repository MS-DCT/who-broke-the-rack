import { useEffect, useState } from "react";

const API_BASE = "http://192.168.100.206:8000";

const ESCALATION_STEPS = [
  "SOFTWARE_RECOVERY_FAILED",
  "ESCALATION_REQUIRED",
  "SPARE_ACTIVATING",
  "PXE",
  "CONFIGURING",
  "READY",
];

const INCIDENT_STATES = [
  "DETECTED",
  "INVESTIGATING",
  "ROOT_CAUSE_FOUND",
  "RECOVERING",
  "ESCALATING",
  "VERIFYING",
  "CLOSED",
];

function IncidentPanel({ onDiagnosisComplete, onPlatformStateChange }) {
  const [serverId, setServerId] = useState("server-207");
  const [incident, setIncident] = useState(null);
  const [diagnosis, setDiagnosis] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [eventCount, setEventCount] = useState(0);
  const [recovery, setRecovery] = useState(null);
  const [recoveryLoading, setRecoveryLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [incidentHistory, setIncidentHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [escalation, setEscalation] = useState(null);

  const loadIncidentHistory = async () => {
    setHistoryLoading(true);
    try {
      const response = await fetch(`${API_BASE}/incidents`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Incident History 조회 실패");
      }

      const sorted = (data.incidents || [])
        .slice()
        .sort((a, b) => new Date(b.started_at || 0) - new Date(a.started_at || 0))
        .slice(0, 5);

      setIncidentHistory(sorted);
    } catch (err) {
      setError(err.message);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    loadIncidentHistory();
  }, [incident?.incident_id, recovery?.status, escalation?.escalation_status]);

  const loadEscalation = async (incidentId) => {
    if (!incidentId) return;

    try {
      const response = await fetch(`${API_BASE}/incidents/${incidentId}/escalation`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Escalation 상태 조회 실패");
      }

      setEscalation(data);
      return data;
    } catch (err) {
      console.error("Escalation polling failed:", err);
    }
  };

  useEffect(() => {
    if (!incident?.incident_id) return;

    loadEscalation(incident.incident_id);

    const timer = setInterval(() => {
      loadEscalation(incident.incident_id);
    }, 2000);

    return () => clearInterval(timer);
  }, [incident?.incident_id]);

  const loadTimeline = async (incidentId) => {
    const response = await fetch(`${API_BASE}/incidents/${incidentId}/timeline`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Timeline 조회 실패");
    }
    setTimeline(data.timeline || []);
    setEventCount(data.event_count || 0);
    return data;
  };

  useEffect(() => {
    if (!incident?.incident_id) return;

    const timer = setInterval(() => {
      loadTimeline(incident.incident_id).catch((err) => {
        console.error("Timeline polling failed:", err);
      });
    }, 2000);

    return () => clearInterval(timer);
  }, [incident?.incident_id]);

  const startIncident = async () => {
    setLoading(true);
    setError("");
    setIncident(null);
    setDiagnosis(null);
    onDiagnosisComplete?.(null);
    setTimeline([]);
    setEventCount(0);
    setRecovery(null);
    setEscalation(null);

    try {
      const startResponse = await fetch(`${API_BASE}/incidents/start/${serverId}`, {
        method: "POST",
      });
      const startData = await startResponse.json();
      if (!startResponse.ok) {
        throw new Error(startData.detail || "Incident 생성 실패");
      }
      setIncident(startData);

      const diagnoseResponse = await fetch(
        `${API_BASE}/incidents/${startData.incident_id}/diagnose`,
        { method: "POST" }
      );
      const diagnoseData = await diagnoseResponse.json();
      if (!diagnoseResponse.ok) {
        throw new Error(diagnoseData.detail || "Diagnosis 실행 실패");
      }

      setDiagnosis(diagnoseData);
      onDiagnosisComplete?.(diagnoseData);
      await loadTimeline(startData.incident_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const refreshTimeline = async () => {
    if (!incident) return;
    try {
      setError("");
      await loadTimeline(incident.incident_id);
    } catch (err) {
      setError(err.message);
    }
  };

  const runRecovery = async (execute, recoveryVars, errorMessage) => {
    if (!incident) return;
    setRecoveryLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE}/incidents/${incident.incident_id}/recovery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          execute,
          recovery_vars: recoveryVars,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || errorMessage);
      }

      setRecovery(data);
      await loadTimeline(incident.incident_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setRecoveryLoading(false);
    }
  };

  const networkRecoveryVars = {
    interface: "eno49",
    gateway: "192.168.100.200",
    routes: [],
    remove_blackhole_routes: ["192.168.100.60/32"],
    verification: {
      required_checks: [
        "nic_link",
        "ip_address",
        "gateway",
        "routes",
        "pxe_reachability",
        "process",
        "listening_port",
        "http_health",
      ],
    },
  };

  const serviceRecoveryVars = {
    profile: "dca_target02_nginx",
    config_content: null,
    http_enabled: true,
  };

  const planNetworkRecovery = () =>
    runRecovery(false, networkRecoveryVars, "Recovery Plan 생성 실패");

  const executeNetworkRecovery = () =>
    runRecovery(true, networkRecoveryVars, "Network Recovery 실행 실패");

  const planServiceRecovery = () =>
    runRecovery(false, serviceRecoveryVars, "Service Recovery Plan 생성 실패");

  const executeServiceRecovery = () =>
    runRecovery(true, serviceRecoveryVars, "Service Recovery 실행 실패");

  const currentIncidentRecord = incidentHistory.find(
    (item) => item.incident_id === incident?.incident_id
  );

  const incidentState = (() => {
    if (recovery?.status === "CLOSED" || currentIncidentRecord?.status === "CLOSED") {
      return "CLOSED";
    }

    if (escalation?.escalation_status === "READY") {
      return "VERIFYING";
    }

    if (escalation?.escalation_status) {
      return "ESCALATING";
    }

    if (recoveryLoading || recovery) {
      return "RECOVERING";
    }

    if (diagnosis?.diagnosis?.diagnosis_status === "MATCHED") {
      return "ROOT_CAUSE_FOUND";
    }

    if (incident) {
      return "INVESTIGATING";
    }

    return "DETECTED";
  })();

  const recoveryTime = (() => {
    if (
      incidentState !== "CLOSED" ||
      !currentIncidentRecord?.started_at ||
      !currentIncidentRecord?.ended_at
    ) {
      return null;
    }

    const start = new Date(currentIncidentRecord.started_at);
    const end = new Date(currentIncidentRecord.ended_at);
    const seconds = Math.max(0, Math.round((end - start) / 1000));

    return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  })();

  useEffect(() => {
    onPlatformStateChange?.({
      incident,
      diagnosis,
      recovery,
      escalation,
      incidentState,
    });
  }, [incident, diagnosis, recovery, escalation, incidentState, onPlatformStateChange]);

  const getEventStatus = (event) => event.status || event.result || "UNKNOWN";

  const renderRecoveryResult = (executeHandler) => (
    <>
      {recovery?.recovery?.mode === "PLAN_ONLY" && (
        <button
          className="execute-recovery-button"
          onClick={executeHandler}
          disabled={recoveryLoading}
        >
          {recoveryLoading ? "REPAIRING / VERIFYING..." : "Execute Recovery"}
        </button>
      )}

      {recovery && (
        <div
          className={`recovery-result ${
            recovery.status === "CLOSED" ? "recovery-success" : ""
          }`}
        >
          <span>{recovery.recovery?.mode}</span>
          <strong>{recovery.recovery?.result}</strong>
          <small>Verification: {recovery.recovery?.verification_status}</small>
          {recovery.status === "CLOSED" && (
            <span className="case-closed">CASE CLOSED</span>
          )}
        </div>
      )}
    </>
  );

  return (
    <section className="incident-section">
      <div className="section-title">
        <div>
          <h2>Live Incident Diagnosis</h2>
          <p>Incident Controller → Diagnosis Engine → Evidence Timeline</p>
        </div>

        {incident && <span className="incident-badge">{incident.incident_id}</span>}
      </div>

      <div className="incident-control">
        <div className="incident-target">
          <label htmlFor="server-select">Target Server</label>
          <select
            id="server-select"
            value={serverId}
            onChange={(e) => setServerId(e.target.value)}
            disabled={loading}
          >
            <option value="server-205">server-205 / dca-target01</option>
            <option value="server-207">server-207 / dca-target02</option>
            <option value="server-208">server-208 / dca-spare01</option>
          </select>
        </div>

        <button className="diagnose-button" onClick={startIncident} disabled={loading}>
          {loading ? "Diagnosing..." : "Start Incident & Diagnose"}
        </button>
      </div>

      {error && <div className="incident-error">{error}</div>}

      {incident && (
        <div className="incident-summary">
          <div>
            <span>Incident ID</span>
            <strong>{incident.incident_id}</strong>
          </div>
          <div>
            <span>Target</span>
            <strong>{incident.host}</strong>
          </div>
          <div>
            <span>Status</span>
            <strong>{diagnosis?.diagnosis?.diagnosis_status || incident.status}</strong>
          </div>
          <div>
            <span>Evidence</span>
            <strong>{diagnosis?.evidence_count ?? 0}</strong>
          </div>
        </div>
      )}

      {incident && (
        <div className="incident-state-machine">
          <div className="state-machine-header">
            <div>
              <span>INCIDENT STATE</span>
              <h3>{incidentState.replaceAll("_", " ")}</h3>
            </div>
          </div>

          <div className="state-machine-steps">
            {INCIDENT_STATES.map((state, index) => {
              const activeIndex = INCIDENT_STATES.indexOf(incidentState);
              const stateClass =
                index < activeIndex
                  ? "complete"
                  : index === activeIndex
                  ? "active"
                  : "pending";

              return (
                <div
                  className={`incident-state incident-state-${stateClass}`}
                  key={state}
                >
                  <div className="incident-state-dot" />
                  <span>{state.replaceAll("_", " ")}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {diagnosis && (
        <div className="root-cause-card">
          <div className="root-cause-header">
            <div>
              <span className="root-cause-label">ROOT CAUSE</span>
              <h3>{diagnosis.root_cause || "Diagnosis Pending"}</h3>
            </div>
            <span className="severity-badge">
              {diagnosis.diagnosis?.severity || "UNKNOWN"}
            </span>
          </div>
          <p>
            <strong>Rule:</strong> {diagnosis.diagnosis?.rule_id || "N/A"}
          </p>
          <p>
            <strong>Recommended Action:</strong>{" "}
            {diagnosis.diagnosis?.recommended_action || "N/A"}
          </p>
        </div>
      )}

      {diagnosis?.diagnosis?.diagnosis_status === "MATCHED" &&
        diagnosis?.diagnosis?.rule_id === "NET-ROUTE-01" && (
          <div className="recovery-card">
            <div>
              <span className="recovery-label">NETWORK RECOVERY</span>
              <h3>Remove Blackhole Route</h3>
              <p>Target: 192.168.100.60/32</p>
            </div>
            <button
              className="recovery-button"
              onClick={planNetworkRecovery}
              disabled={recoveryLoading}
            >
              {recoveryLoading ? "Planning..." : "Plan Recovery"}
            </button>
            {renderRecoveryResult(executeNetworkRecovery)}
          </div>
        )}

      {diagnosis?.diagnosis?.diagnosis_status === "MATCHED" &&
        diagnosis?.diagnosis?.rule_id === "SVC-HTTP-01" && (
          <div className="recovery-card">
            <div>
              <span className="recovery-label">SERVICE RECOVERY</span>
              <h3>Recover Nginx Service</h3>
              <p>Target: dca-target02 / nginx.service</p>
            </div>
            <button
              className="recovery-button"
              onClick={planServiceRecovery}
              disabled={recoveryLoading}
            >
              {recoveryLoading ? "Planning..." : "Plan Recovery"}
            </button>
            {renderRecoveryResult(executeServiceRecovery)}
          </div>
        )}

      {escalation?.escalation_status && (
        <div className="escalation-card">
          <div className="escalation-header">
            <div>
              <span className="escalation-label">RECOVERY ESCALATION</span>
              <h3>Physical Recovery Progress</h3>
            </div>
            <span className="escalation-level">{escalation.escalation_level || "N/A"}</span>
          </div>

          <div className="escalation-progress">
            {ESCALATION_STEPS.map((step, index) => {
              const activeIndex = ESCALATION_STEPS.indexOf(escalation.escalation_status);
              const state =
                index < activeIndex
                  ? "complete"
                  : index === activeIndex
                  ? "active"
                  : "pending";

              return (
                <div
                  className={`escalation-step escalation-step-${state}`}
                  key={step}
                >
                  <div className="escalation-dot" />
                  <span>{step.replaceAll("_", " ")}</span>
                </div>
              );
            })}
          </div>

          <div className="escalation-current">
            <span>Current Status</span>
            <strong>{escalation.escalation_status.replaceAll("_", " ")}</strong>
          </div>
        </div>
      )}

      {incidentState === "CLOSED" && (
        <div className="final-case-result">
          <div>
            <span>FINAL RESULT</span>
            <h2>CASE CLOSED</h2>
          </div>
          <div className="final-recovery-time">
            <span>Recovery Time</span>
            <strong>{recoveryTime || "Recorded"}</strong>
          </div>
        </div>
      )}

      <div className="incident-history-section">
        <div className="incident-history-header">
          <div>
            <h3>Incident History</h3>
            <p>Recent incidents</p>
          </div>
          <button
            className="refresh-button"
            onClick={loadIncidentHistory}
            disabled={historyLoading}
          >
            {historyLoading ? "Loading..." : "Refresh History"}
          </button>
        </div>

        <div className="incident-history-list">
          {incidentHistory.length === 0 ? (
            <div className="history-empty">No incidents recorded</div>
          ) : (
            incidentHistory.map((item) => (
              <div className="history-item" key={item.incident_id}>
                <span className="history-id">{item.incident_id}</span>
                <span className="history-server">{item.server_id}</span>
                <span
                  className={`history-status history-status-${(
                    item.status || "UNKNOWN"
                  ).toLowerCase()}`}
                >
                  {item.status || "UNKNOWN"}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {incident && (
        <div className="live-timeline-section">
          <div className="live-timeline-header">
            <div>
              <h3>Incident Evidence Timeline</h3>
              <p>{eventCount} events recorded</p>
            </div>
            <button className="refresh-button" onClick={refreshTimeline} disabled={loading}>
              Refresh Timeline
            </button>
          </div>

          <div className="live-timeline">
            {timeline.map((event, index) => {
              const status = getEventStatus(event);
              return (
                <div className="live-event" key={`${event.type}-${index}`}>
                  <div className="event-marker" />
                  <div className="event-content">
                    <div className="event-top">
                      <div>
                        <span className="event-type">{event.type}</span>
                        <h4>{event.name || "Event"}</h4>
                      </div>
                      <span className="event-status">{status}</span>
                    </div>
                    {event.layer && <span className="event-layer">{event.layer}</span>}
                    {event.details && <p>{event.details}</p>}
                    {event.timestamp && <small>{event.timestamp}</small>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

export default IncidentPanel;
