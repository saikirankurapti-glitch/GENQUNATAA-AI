"use client";

import { FormEvent, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AuthPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/v1/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(mode === "register" ? { email, password, name } : { email, password }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Authentication failed");
      window.location.href = "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="main" style={{ maxWidth: 520, margin: "0 auto", paddingTop: 80 }}>
      <div className="card hero">
        <div className="eyebrow">GenQuantaa AI</div>
        <h1 className="title">{mode === "login" ? "Sign in" : "Create account"}</h1>
        <p className="subtitle">Your workspace, live sessions, documents and visual context are protected by your account.</p>
        <form onSubmit={submit} style={{ marginTop: 24 }}>
          {mode === "register" && <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" required style={{ width: "100%", marginBottom: 12, padding: 12 }} />}
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" placeholder="Email" required style={{ width: "100%", marginBottom: 12, padding: 12 }} />
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="Password" minLength={8} required style={{ width: "100%", marginBottom: 12, padding: 12 }} />
          {error && <div className="card" style={{ marginBottom: 12 }}>{error}</div>}
          <button className="primary" type="submit" disabled={loading}>{loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
        </form>
        <button className="secondary" style={{ marginTop: 12 }} onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
          {mode === "login" ? "Create a new account" : "I already have an account"}
        </button>
      </div>
    </main>
  );
}
