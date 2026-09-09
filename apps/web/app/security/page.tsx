"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, LogOut, Shield, Smartphone, Trash2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AuthSession = {
  id: string;
  created_at: string;
  last_seen_at: string | null;
  expires_at: string;
  current: boolean;
  device: string;
};

function formatDate(value: string | null) {
  if (!value) return "Never";
  return new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

export default function SecurityPage() {
  const [sessions, setSessions] = useState<AuthSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadSessions() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/v1/auth/sessions`, { credentials: "include", cache: "no-store" });
      if (response.status === 401) {
        window.location.href = "/auth?next=/security";
        return;
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to load sessions");
      setSessions(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load sessions");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSessions();
  }, []);

  async function revoke(id: string) {
    setBusy(id);
    setMessage("");
    setError("");
    try {
      const response = await fetch(`${API}/api/v1/auth/sessions/${id}`, { method: "DELETE", credentials: "include" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to revoke session");
      if (data.current) {
        window.location.href = "/auth";
        return;
      }
      setMessage("Session revoked successfully.");
      await loadSessions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to revoke session");
    } finally {
      setBusy(null);
    }
  }

  async function revokeAll() {
    if (!window.confirm("Sign out from every GenQuantaa session on every device?")) return;
    setBusy("all");
    setMessage("");
    setError("");
    try {
      const response = await fetch(`${API}/api/v1/auth/sessions/revoke-all`, { method: "POST", credentials: "include" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to sign out all devices");
      window.location.href = "/auth?next=/";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to sign out all devices");
      setBusy(null);
    }
  }

  return (
    <main className="shell" style={{ minHeight: "100vh", display: "block" }}>
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "48px 24px" }}>
        <button className="secondary" onClick={() => (window.location.href = "/")} style={{ marginBottom: 24 }}>
          <ArrowLeft size={16} /> Back to workspace
        </button>
        <div className="top" style={{ marginBottom: 24 }}>
          <div>
            <div className="eyebrow">Account security</div>
            <h1 className="title">Active sessions</h1>
            <div className="subtitle">Review where your GenQuantaa account is signed in and revoke access you no longer recognize.</div>
          </div>
          <div className="pill"><Shield size={14} /> Protected</div>
        </div>
        <section className="card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, marginBottom: 20 }}>
            <div>
              <div className="eyebrow">Signed-in devices</div>
              <h2 style={{ margin: "6px 0 0" }}>{sessions.length} active session{sessions.length === 1 ? "" : "s"}</h2>
            </div>
            <button className="secondary" onClick={() => void revokeAll()} disabled={busy === "all" || sessions.length === 0}>
              <LogOut size={16} /> {busy === "all" ? "Signing out…" : "Sign out all devices"}
            </button>
          </div>
          {message && <div style={{ padding: 12, marginBottom: 16, borderRadius: 10, border: "1px solid rgba(80,200,120,.3)" }}><CheckCircle2 size={15} style={{ verticalAlign: "-3px", marginRight: 7 }} />{message}</div>}
          {error && <div style={{ padding: 12, marginBottom: 16, borderRadius: 10, border: "1px solid rgba(220,80,80,.35)" }}>{error}</div>}
          {loading ? <p className="subtitle">Loading active sessions…</p> : sessions.length === 0 ? <p className="subtitle">No active sessions were found.</p> : (
            <div style={{ display: "grid", gap: 12 }}>
              {sessions.map((session) => (
                <div key={session.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, padding: 16, border: "1px solid rgba(127,127,127,.18)", borderRadius: 14 }}>
                  <div style={{ display: "flex", gap: 13, alignItems: "flex-start", minWidth: 0 }}>
                    <div style={{ padding: 9, borderRadius: 10, background: "rgba(127,127,127,.1)" }}><Smartphone size={18} /></div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 650 }}>{session.device} {session.current && <span className="pill" style={{ marginLeft: 8, fontSize: 11, padding: "4px 8px" }}>This device</span>}</div>
                      <div className="subtitle" style={{ marginTop: 5, fontSize: 13 }}>Signed in {formatDate(session.created_at)} · Last active {formatDate(session.last_seen_at)}</div>
                      <div className="subtitle" style={{ marginTop: 3, fontSize: 12 }}>Expires {formatDate(session.expires_at)}</div>
                    </div>
                  </div>
                  <button className="secondary" onClick={() => void revoke(session.id)} disabled={busy === session.id} style={{ flexShrink: 0 }}>
                    <Trash2 size={15} /> {busy === session.id ? "Revoking…" : session.current ? "Sign out" : "Revoke"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
        <section className="card" style={{ marginTop: 18 }}>
          <div className="eyebrow">Security note</div>
          <p className="subtitle" style={{ marginBottom: 0 }}>Session tokens are stored server-side as hashes. Revoking a session invalidates that token immediately, even if an old browser cookie is still present.</p>
        </section>
      </div>
    </main>
  );
}
