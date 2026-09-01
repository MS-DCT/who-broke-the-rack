import { useEffect, useState } from "react";
import "./App.css";
import IncidentPanel from "./IncidentPanel";

function App() {
  const [servers, setServers] = useState([]);
  const [evidence, setEvidence] = useState([]);
  const [error, setError] = useState("");
  const [liveDiagnosis, setLiveDiagnosis] = useState(null);

  const CURRENT_INCIDENT = "DAY2-207";

  useEffect(() => {
    Promise.all([
      fetch("http://192.168.100.206:8000/servers"),
      fetch("http://192.168.100.206:8000/evidence"),
    ])
      .then(async ([serversResponse, evidenceResponse]) => {
        if (!serversResponse.ok || !evidenceResponse.ok) {
          throw new Error("FastAPI 연결 실패");
        }

        const serversData = await serversResponse.json();
        const evidenceData = await evidenceResponse.json();

        setServers(serversData.servers);
        setEvidence(evidenceData.evidence);
      })
      .catch((err) => {
        setError(err.message);
      });
  }, []);

  const day2Evidence = evidence.filter(
    (item) => item.incident_id === CURRENT_INCIDENT
  );

  const getStatusFromItems = (items) => {
    const validItems = items.filter(
      (item) => item.result !== "SKIP"
    );

    if (validItems.length === 0) return "UNKNOWN";
    if (validItems.some((item) => item.result === "FAIL")) return "SUSPECT";
    if (validItems.some((item) => item.result === "WARN")) return "SUSPECT";
    if (validItems.some((item) => item.result === "UNKNOWN")) return "UNKNOWN";
    if (validItems.every((item) => item.result === "PASS")) return "NORMAL";
    return "UNKNOWN";
  };

  const powerEvidence = day2Evidence.filter(
    (item) =>
      item.layer === "HARDWARE" &&
      item.check_name.toLowerCase().includes("power")
  );

  const memoryEvidence = day2Evidence.filter(
    (item) => item.check_name.toLowerCase().includes("memory")
  );

  const storageEvidence = day2Evidence.filter(
    (item) =>
      item.check_name.toLowerCase().includes("storage") ||
      item.check_name.toLowerCase().includes("disk")
  );

  const networkEvidence = day2Evidence.filter(
    (item) => item.layer === "NETWORK"
  );

  const osEvidence = day2Evidence.filter(
    (item) =>
      item.layer === "OS" &&
      !item.check_name.toLowerCase().includes("memory")
  );

  const serviceEvidence = day2Evidence.filter(
    (item) => item.layer === "SERVICE"
  );

  const suspects = [
    { name: "Power", status: getStatusFromItems(powerEvidence) },
    { name: "Memory", status: getStatusFromItems(memoryEvidence) },
    { name: "Storage", status: getStatusFromItems(storageEvidence) },
    { name: "Network", status: getStatusFromItems(networkEvidence) },
    { name: "OS", status: getStatusFromItems(osEvidence) },
    { name: "Service", status: getStatusFromItems(serviceEvidence) },
  ];

  const culpritFromRule = (ruleId) => {
    if (!ruleId) return null;
    if (ruleId.startsWith("HW-STORAGE")) return "Storage";
    if (ruleId.startsWith("BOOT-OS")) return "OS";
    if (ruleId.startsWith("NET-")) return "Network";
    if (ruleId.startsWith("SVC-")) return "Service";
    return null;
  };

  const culpritName =
    liveDiagnosis?.diagnosis?.diagnosis_status === "MATCHED"
      ? culpritFromRule(liveDiagnosis?.diagnosis?.rule_id)
      : null;

  const getStatusLabel = (status) => {
    if (status === "NORMAL") return "정상";
    if (status === "SUSPECT") return "의심";
    return "조사 전";
  };

  const getSuspectLabel = (suspect) => {
    if (culpritName === suspect.name) return "CULPRIT FOUND";
    if (culpritName && suspect.status === "NORMAL") return "CLEARED";
    return getStatusLabel(suspect.status);
  };

  return (
    <div className="dashboard">
      <header>
        <h1>WHO BROKE THE RACK?</h1>
        <p>Data Center Troubleshooting & Automated Recovery Platform</p>
      </header>

      {error && <div className="error">{error}</div>}

      <IncidentPanel onDiagnosisComplete={setLiveDiagnosis} />

      <section>
        <h2>Rack Overview</h2>
        <div className="server-grid">
          {servers.map((server) => (
            <div className="server-card" key={server.server_id}>
              <div className="card-header">
                <h3>{server.hostname}</h3>
                <span className="status">{server.status}</span>
              </div>
              <p><strong>Server ID</strong><span>{server.server_id}</span></p>
              <p><strong>Role</strong><span>{server.role}</span></p>
              <p><strong>Data Plane IP</strong><span>{server.ip}</span></p>
            </div>
          ))}
        </div>
      </section>

      <section className="suspect-section">
        <div className="section-title">
          <div>
            <h2>Suspect Cards</h2>
            <p>
              Incident: <strong>{CURRENT_INCIDENT}</strong> / Target:{" "}
              <strong>server-207</strong>
            </p>
          </div>
        </div>

        <div className="suspect-grid">
          {suspects.map((suspect) => {
            const isCulprit = culpritName === suspect.name;
            const isCleared =
              Boolean(culpritName) &&
              !isCulprit &&
              suspect.status === "NORMAL";

            return (
              <div
                className={`suspect-card suspect-${suspect.status.toLowerCase()} ${
                  isCulprit ? "suspect-culprit" : ""
                } ${
                  isCleared ? "suspect-cleared" : ""
                }`}
                key={suspect.name}
              >
                <span className="suspect-name">{suspect.name}</span>
                <span
                  className={`suspect-status suspect-status-${suspect.status.toLowerCase()} ${
                    isCulprit ? "culprit-status" : ""
                  }`}
                >
                  {getSuspectLabel(suspect)}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      <section className="evidence-section">
        <div className="section-title">
          <div>
            <h2>Evidence Timeline</h2>
            <p>Real Diagnostic Evidence — {CURRENT_INCIDENT}</p>
          </div>
          <span className="evidence-count">
            {day2Evidence.length} Evidence
          </span>
        </div>

        <div className="timeline">
          {day2Evidence.map((item, index) => (
            <div className="evidence-card" key={index}>
              <div className="evidence-top">
                <div>
                  <span className="layer">{item.layer}</span>
                  <h3>{item.check_name}</h3>
                </div>
                <span className={`result result-${item.result.toLowerCase()}`}>
                  {item.result}
                </span>
              </div>
              <div className="evidence-details">
                <span>{item.incident_id}</span>
                <span>{item.server_id}</span>
                <span>Severity: {item.severity}</span>
              </div>
              <p className="detail-text">{item.details}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default App;
