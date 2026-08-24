import { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [servers, setServers] = useState([]);
  const [evidence, setEvidence] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      fetch("http://192.168.100.206:8000/servers"),
      fetch("http://192.168.100.206:8000/evidence")
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

  return (
    <div className="dashboard">
      <header>
        <h1>WHO BROKE THE RACK?</h1>
        <p>Data Center Troubleshooting & Automated Recovery Platform</p>
      </header>

      {error && <div className="error">{error}</div>}

      <section>
        <h2>Rack Overview</h2>

        <div className="server-grid">
          {servers.map((server) => (
            <div className="server-card" key={server.server_id}>
              <div className="card-header">
                <h3>{server.hostname}</h3>
                <span className="status">{server.status}</span>
              </div>

              <p>
                <strong>Server ID</strong>
                <span>{server.server_id}</span>
              </p>

              <p>
                <strong>Role</strong>
                <span>{server.role}</span>
              </p>

              <p>
                <strong>Data Plane IP</strong>
                <span>{server.ip}</span>
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="evidence-section">
        <h2>Evidence Timeline</h2>

        <div className="timeline">
          {evidence.map((item, index) => (
            <div className="evidence-card" key={index}>
              <div className="evidence-top">
                <div>
                  <span className="layer">{item.layer}</span>
                  <h3>{item.check_name}</h3>
                </div>

                <span
                  className={`result result-${item.result.toLowerCase()}`}
                >
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
