"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, RefreshCw } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AuditLog = {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  details: Record<string, unknown>;
  ip_address: string;
  user_agent: string;
  created_at: string;
};

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/v1/audit/logs?limit=200`, { credentials: "include" });
      const data = await response.json();
      if (response.status === 401) { window.location.href = "/auth?next=/audit"; return; }
      if (!response.ok) throw new Error(data.detail || "Unable to load audit logs");
      setLogs(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load audit logs");
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  return <main className="main" style={{ maxWidth: 1180, margin: "0 auto", padding: 32 }}>
    <div className="top">
      <div><div className="eyebrow">Governance & security</div><h1 className="title">Audit Log</h1><div className="subtitle">Review privileged workspace activity and role changes.</div></div>
      <button className="secondary" onClick={load}><RefreshCw size={15}/> Refresh</button>
    </div>
    <section className="card" style={{ marginTop: 24 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 18 }}><ShieldCheck size={18}/><strong>Activity</strong><span className="subtitle">{logs.length} events</span></div>
      {loading && <p className="subtitle">Loading audit events…</p>}
      {error && <p>{error}</p>}
      {!loading && !error && logs.length === 0 && <p className="subtitle">No audit events yet.</p>}
      {!loading && !error && logs.length > 0 && <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr><th align="left">Time</th><th align="left">Action</th><th align="left">Resource</th><th align="left">Actor</th><th align="left">Details</th></tr></thead><tbody>{logs.map(log => <tr key={log.id} style={{ borderTop: "1px solid rgba(255,255,255,.08)" }}><td style={{ padding: "14px 8px", whiteSpace: "nowrap" }}>{new Date(log.created_at).toLocaleString()}</td><td style={{ padding: "14px 8px" }}><strong>{log.action}</strong></td><td style={{ padding: "14px 8px" }}>{log.resource_type || "—"}{log.resource_id ? ` · ${log.resource_id.slice(0, 8)}` : ""}</td><td style={{ padding: "14px 8px" }}>{log.actor_user_id ? log.actor_user_id.slice(0, 8) : "System"}</td><td style={{ padding: "14px 8px", maxWidth: 360, wordBreak: "break-word" }}>{Object.keys(log.details).length ? JSON.stringify(log.details) : "—"}</td></tr>)}</tbody></table></div>}
    </section>
  </main>;
}
