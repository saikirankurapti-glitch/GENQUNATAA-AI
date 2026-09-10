"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, CheckCircle2, Mic, Radio, Target, TrendingUp } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Evaluation = {
  question_id: string;
  candidate_answer: string;
  candidate_score: number;
  correctness_score: number;
  relevance_score: number;
  completeness_score: number;
  structure_score: number;
  technical_depth_score: number;
  communication_score: number;
  evaluation_feedback: string;
  missing_concepts: string[];
};

const pct = (value: number) => `${Math.round(Math.max(0, Math.min(1, value || 0)) * 100)}%`;

export default function LiveEvaluationPage() {
  const ws = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [capture, setCapture] = useState("Waiting for a detected question");
  const [chars, setChars] = useState(0);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const socket = new WebSocket(API.replace(/^http/, "ws") + "/api/v1/realtime/ws");
    ws.current = socket;
    socket.onopen = () => {
      setConnected(true);
      setError("");
      socket.send(JSON.stringify({ type: "start", auto_answer: true, answer_mode: "concise", candidate_capture: "auto" }));
    };
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setError("Realtime connection failed. Make sure the backend is running and Gemini is configured.");
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "candidate_capture") {
        setChars(Number(data.chars || 0));
        setCapture(data.active ? "Capturing candidate answer…" : "Waiting for a detected question");
      }
      if (data.type === "candidate_answer") {
        setEvaluations((items) => [data.data, ...items]);
        setChars(0);
        setCapture("Candidate answer evaluated");
      }
      if (data.type === "question_detected") setCapture("Question detected — waiting for candidate answer");
      if (data.type === "candidate_evaluation_error" || data.type === "error") setError(data.message || "Candidate evaluation failed");
    };
    return () => socket.close();
  }, []);

  const latest = evaluations[0];
  const dimensions = latest ? [
    ["Correctness", latest.correctness_score],
    ["Relevance", latest.relevance_score],
    ["Completeness", latest.completeness_score],
    ["Structure", latest.structure_score],
    ["Technical depth", latest.technical_depth_score],
    ["Communication", latest.communication_score],
  ] as const : [];

  return <main className="main">
    <div className="top">
      <div>
        <div className="eyebrow"><Radio size={14} /> Live Candidate Evaluation</div>
        <h1 className="title">Automatic Answer Capture</h1>
        <div className="subtitle">Detected question → candidate speech → automatic evaluation → actionable coaching.</div>
      </div>
      <span className="pill"><Radio size={14} /> {connected ? "Connected" : "Offline"}</span>
    </div>

    {error && <div className="card" style={{ marginBottom: 18 }}>{error}</div>}

    <div className="grid">
      <section>
        <div className="card hero">
          <div className="eyebrow"><Mic size={14} /> Candidate capture</div>
          <h2>{capture}</h2>
          <p className="subtitle">The realtime backend captures non-question speech after a detected interview question. Speaker-tagged clients can also send explicit candidate segments.</p>
          <div className="row" style={{ marginTop: 18 }}><span>Captured characters</span><b>{chars}</b></div>
          <div className="row" style={{ marginTop: 8 }}><span>Evaluated answers</span><b>{evaluations.length}</b></div>
        </div>

        {latest && <div className="card" style={{ marginTop: 20 }}>
          <div className="eyebrow"><CheckCircle2 size={14} /> Latest evaluation</div>
          <div style={{ fontSize: 46, fontWeight: 700, marginTop: 8 }}>{pct(latest.candidate_score)}</div>
          <p><strong>Candidate answer</strong><br />{latest.candidate_answer}</p>
          <div className="grid" style={{ marginTop: 14 }}>
            {dimensions.map(([name, value]) => <div className="card" key={name}><span className="label">{name}</span><div style={{ fontSize: 26, fontWeight: 700 }}>{pct(value)}</div><div style={{ height: 7, background: "var(--border)", borderRadius: 99, marginTop: 8 }}><div style={{ width: pct(value), height: "100%", background: "currentColor", borderRadius: 99 }} /></div></div>)}
          </div>
          <div style={{ marginTop: 16 }}><h3><TrendingUp size={15} /> Coaching feedback</h3><p>{latest.evaluation_feedback || "No additional feedback."}</p></div>
          <div style={{ marginTop: 16 }}><h3><Target size={15} /> Missing concepts / evidence</h3>{latest.missing_concepts.length ? <ul>{latest.missing_concepts.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="muted">No major gaps detected.</p>}</div>
        </div>}

        <div className="card" style={{ marginTop: 20 }}><div className="eyebrow">Evaluation history</div>{evaluations.length === 0 ? <p className="muted">No candidate answers evaluated yet. Start the Live Copilot and answer a detected question.</p> : evaluations.map((item, index) => <div className="row" key={`${item.question_id}-${index}`}><span>Answer {evaluations.length - index}<br /><small className="muted">{item.candidate_answer.slice(0, 120)}{item.candidate_answer.length > 120 ? "…" : ""}</small></span><b>{pct(item.candidate_score)}</b></div>)}</div>
      </section>

      <aside><div className="card"><div className="eyebrow">How automatic capture works</div><ol><li>Gemini Live transcribes the conversation.</li><li>GenQuantaa detects the interviewer question boundary.</li><li>Subsequent non-question speech is associated with that question.</li><li>The candidate answer is scored across six dimensions.</li><li>Results are persisted to the interview session.</li></ol><p className="muted">For the most reliable speaker separation, a speaker-tagged client can send <code>candidate_text</code> and <code>candidate_end</code> events.</p></div><button className="secondary" style={{ marginTop: 20 }} onClick={() => window.location.href = "/live"}><ArrowLeft size={15} /> Back to Live Copilot</button></aside>
    </div>
  </main>;
}
