import { useState } from "react";

const API_BASE = "http://192.168.100.206:8000";

function IncidentPanel() {
  const [serverId, setServerId] = useState("server-207");
  const [incident, setIncident] = useState(null);
  const [diagnosis, setDiagnosis] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [eventCount, setEventCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadTimeline = async (incidentId) => {
    const response = await fetch(
      `${API_BASE}/incidents/${incidentId}/timeline`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Timeline 조회 실패"
      );
    }

    setTimeline(data.timeline || []);
    setEventCount(data.event_count || 0);

    return data;
  };

  const startIncident = async () => {
    setLoading(true);
    setError("");
    setIncident(null);
    setDiagnosis(null);
    setTimeline([]);
    setEventCount(0);

    try {
      // 1. Incident 생성
      const startResponse = await fetch(
        `${API_BASE}/incidents/start/${serverId}`,
        {
          method: "POST",
        }
      );

      const startData = await startResponse.json();

      if (!startResponse.ok) {
        throw new Error(
          startData.detail || "Incident 생성 실패"
        );
      }

      setIncident(startData);

      // 2. B Diagnosis Engine 실행
      const diagnoseResponse = await fetch(
        `${API_BASE}/incidents/${startData.incident_id}/diagnose`,
        {
          method: "POST",
        }
      );

      const diagnoseData =
        await diagnoseResponse.json();

      if (!diagnoseResponse.ok) {
        throw new Error(
          diagnoseData.detail || "Diagnosis 실행 실패"
        );
      }

      setDiagnosis(diagnoseData);

      // 3. C Timeline 조회
      await loadTimeline(
        startData.incident_id
      );
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

      await loadTimeline(
        incident.incident_id
      );
    } catch (err) {
      setError(err.message);
    }
  };

  const getEventStatus = (event) => {
    return (
      event.status ||
      event.result ||
      "UNKNOWN"
    );
  };

  return (
    <section className="incident-section">
      <div className="section-title">
        <div>
          <h2>Live Incident Diagnosis</h2>
          <p>
            Incident Controller → Diagnosis Engine →
            Evidence Timeline
          </p>
        </div>

        {incident && (
          <span className="incident-badge">
            {incident.incident_id}
          </span>
        )}
      </div>

      <div className="incident-control">
        <div className="incident-target">
          <label htmlFor="server-select">
            Target Server
          </label>

          <select
            id="server-select"
            value={serverId}
            onChange={(e) =>
              setServerId(e.target.value)
            }
            disabled={loading}
          >
            <option value="server-205">
              server-205 / dca-target01
            </option>

            <option value="server-207">
              server-207 / dca-target02
            </option>

            <option value="server-208">
              server-208 / dca-spare01
            </option>
          </select>
        </div>

        <button
          className="diagnose-button"
          onClick={startIncident}
          disabled={loading}
        >
          {loading
            ? "Diagnosing..."
            : "Start Incident & Diagnose"}
        </button>
      </div>

      {error && (
        <div className="incident-error">
          {error}
        </div>
      )}

      {incident && (
        <div className="incident-summary">
          <div>
            <span>Incident ID</span>
            <strong>
              {incident.incident_id}
            </strong>
          </div>

          <div>
            <span>Target</span>
            <strong>
              {incident.host}
            </strong>
          </div>

          <div>
            <span>Status</span>
            <strong>
              {diagnosis?.diagnosis
                ?.diagnosis_status ||
                incident.status}
            </strong>
          </div>

          <div>
            <span>Evidence</span>
            <strong>
              {diagnosis?.evidence_count ?? 0}
            </strong>
          </div>
        </div>
      )}

      {diagnosis && (
        <div className="root-cause-card">
          <div className="root-cause-header">
            <div>
              <span className="root-cause-label">
                ROOT CAUSE
              </span>

              <h3>
                {diagnosis.root_cause ||
                  "Diagnosis Pending"}
              </h3>
            </div>

            <span className="severity-badge">
              {diagnosis.diagnosis
                ?.severity || "UNKNOWN"}
            </span>
          </div>

          <p>
            <strong>Rule:</strong>{" "}
            {diagnosis.diagnosis
              ?.rule_id || "N/A"}
          </p>

          <p>
            <strong>
              Recommended Action:
            </strong>{" "}
            {diagnosis.diagnosis
              ?.recommended_action ||
              "N/A"}
          </p>
        </div>
      )}

      {incident && (
        <div className="live-timeline-section">
          <div className="live-timeline-header">
            <div>
              <h3>Incident Evidence Timeline</h3>
              <p>
                {eventCount} events recorded
              </p>
            </div>

            <button
              className="refresh-button"
              onClick={refreshTimeline}
              disabled={loading}
            >
              Refresh Timeline
            </button>
          </div>

          <div className="live-timeline">
            {timeline.map(
              (event, index) => {
                const status =
                  getEventStatus(event);

                return (
                  <div
                    className="live-event"
                    key={`${event.type}-${index}`}
                  >
                    <div className="event-marker" />

                    <div className="event-content">
                      <div className="event-top">
                        <div>
                          <span className="event-type">
                            {event.type}
                          </span>

                          <h4>
                            {event.name ||
                              "Event"}
                          </h4>
                        </div>

                        <span className="event-status">
                          {status}
                        </span>
                      </div>

                      {event.layer && (
                        <span className="event-layer">
                          {event.layer}
                        </span>
                      )}

                      {event.details && (
                        <p>
                          {event.details}
                        </p>
                      )}

                      {event.timestamp && (
                        <small>
                          {event.timestamp}
                        </small>
                      )}
                    </div>
                  </div>
                );
              }
            )}
          </div>
        </div>
      )}
    </section>
  );
}

export default IncidentPanel;
