"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, ExternalLink, Link2, Play, Radio, Square } from "lucide-react";

type Provider = { id: string; name: string };
type MeetingState = { active?: boolean; provider?: string | null; provider_name?: string | null; meeting_url?: string | null; session_id?: string | null; title?: string | null; status?: string; error?: string };

declare global {
  interface Window {
    genquantaa?: {
      detectMeetingProvider?: (url: string) => Promise<Provider | null>;
      getMeetingProviders?: () => Promise<Provider[]>;
      startMeetingMonitor?: (payload: { meetingUrl: string; title?: string; autoAnswer?: boolean; answerMode?: string; openMeeting?: boolean }) => Promise<MeetingState>;
      stopMeetingMonitor?: () => Promise<MeetingState>;
      getMeetingState?: () => Promise<MeetingState>;
      onMeetingState?: (callback: (state: MeetingState) => void) => () => void;
    };
  }
}

const fallbackProviders: Provider[] = [
  { id: "google-meet", name: "Google Meet" },
  { id: "microsoft-teams", name: "Microsoft Teams" },
  { id: "zoom", name: "Zoom" },
  { id: "webex", name: "Webex" },
  { id: "hackerrank", name: "HackerRank" },
  { id: "leetcode", name: "LeetCode" },
];

export default function MeetingPage() {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [autoAnswer, setAutoAnswer] = useState(true);
  const [answerMode, setAnswerMode] = useState("concise");
  const [provider, setProvider] = useState<Provider | null>(null);
  const [providers, setProviders] = useState<Provider[]>(fallbackProviders);
  const [state, setState] = useState<MeetingState>({ status: "idle" });
  const [error, setError] = useState("");

  useEffect(() => {
    let unsubscribe: (() => void) | undefined;
    window.genquantaa?.getMeetingProviders?.().then((items) => { if (items?.length) setProviders(items); });
    window.genquantaa?.getMeetingState?.().then(setState);
    unsubscribe = window.genquantaa?.onMeetingState?.(setState);
    return () => unsubscribe?.();
  }, []);

  async function detect() {
    setError("");
    if (!url.trim()) { setProvider(null); return; }
    const result = await window.genquantaa?.detectMeetingProvider?.(url.trim());
    setProvider(result || null);
    if (!result) setError("Enter a supported meeting or coding interview URL.");
  }

  async function start() {
    setError("");
    await detect();
    const detected = await window.genquantaa?.detectMeetingProvider?.(url.trim());
    if (!detected) return;
    const result = await window.genquantaa?.startMeetingMonitor?.({ meetingUrl: url.trim(), title: title.trim(), autoAnswer, answerMode, openMeeting: true });
    if (result) { setState(result); if (result.status === "error") setError(result.error || "Could not start meeting session."); }
  }

  async function stop() {
    const result = await window.genquantaa?.stopMeetingMonitor?.();
    if (result) setState(result);
  }

  return <main className="main">
    <div className="top"><div><div className="eyebrow">Session orchestration</div><h1 className="title">Meeting Auto-Session</h1><div className="subtitle">Recognize a supported interview URL, create a session, open the meeting, and route the copilot to the desktop overlay.</div></div><span className="pill"><Radio size={14} /> {state.active ? "Monitoring" : "Ready"}</span></div>

    {error && <div className="card" style={{ marginBottom: 18 }}>{error}</div>}

    <div className="grid"><section>
      <div className="card hero"><div><div className="eyebrow"><Link2 size={14} /> Meeting detection</div><h2>Start the interview workflow from one link.</h2><p className="subtitle">GenQuantaa identifies the provider before creating the session. The meeting opens in your normal browser; microphone capture still requires an explicit action in Live Copilot.</p></div>
        <div style={{ marginTop: 20 }}><label className="muted" htmlFor="meeting-url">Meeting / interview URL</label><input id="meeting-url" value={url} onChange={(e) => setUrl(e.target.value)} onBlur={detect} placeholder="https://meet.google.com/..." style={{ width: "100%", marginTop: 6 }} /></div>
        <div className="row" style={{ marginTop: 12 }}><span>Detected provider</span><b>{provider?.name || "Not detected"}</b></div>
        <div style={{ marginTop: 16 }}><label className="muted" htmlFor="session-title">Session title (optional)</label><input id="session-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={provider ? `${provider.name} interview` : "Interview session"} style={{ width: "100%", marginTop: 6 }} /></div>
        <div className="actions" style={{ marginTop: 18 }}><button className="primary" disabled={Boolean(state.active) || !provider} onClick={start}><Play size={16} /> Create & Start Session</button>{state.active && <button className="secondary" onClick={stop}><Square size={16} /> Stop orchestration</button>}</div>
      </div>

      <div className="card" style={{ marginTop: 20 }}><div className="eyebrow">Supported platforms</div><div className="list">{providers.map((item) => <div className="row" key={item.id}><span>{item.name}</span><b>Ready</b></div>)}</div></div>
    </section>

    <aside>
      <div className="card"><div className="eyebrow">Automation policy</div><div className="row" style={{ marginTop: 12 }}><span><strong>Automatic answers</strong><br /><small className="muted">Use detected question boundaries to generate answers.</small></span><button className={autoAnswer ? "primary" : "secondary"} onClick={() => setAutoAnswer((value) => !value)}>{autoAnswer ? "ON" : "OFF"}</button></div><div style={{ marginTop: 14 }}><label className="muted" htmlFor="meeting-answer-mode">Answer style</label><select id="meeting-answer-mode" value={answerMode} onChange={(e) => setAnswerMode(e.target.value)} style={{ width: "100%", marginTop: 6, padding: 10, borderRadius: 10, background: "var(--panel, #fff)", color: "inherit", border: "1px solid rgba(127,133,0,.25)" }}><option value="concise">Concise — fast spoken response</option><option value="detailed">Detailed — implementation depth</option><option value="star">STAR — behavioral/project structure</option><option value="technical">Technical — architecture & trade-offs</option></select></div></div>
      <div className="card" style={{ marginTop: 20 }}><div className="eyebrow">Current orchestration</div><div className="list"><div className="row"><span>Status</span><b>{state.status || "idle"}</b></div><div className="row"><span>Provider</span><b>{state.provider_name || "—"}</b></div><div className="row"><span>Session</span><b>{state.session_id ? state.session_id.slice(0, 8) : "—"}</b></div><div className="row"><span>Title</span><b>{state.title || "—"}</b></div></div>{state.active && <p className="muted" style={{ marginTop: 14 }}>Meeting opened. Switch to Live Copilot and press <strong>Start microphone</strong> after granting browser permission.</p>}</div>
      <div className="card" style={{ marginTop: 20 }}><div className="eyebrow"><ExternalLink size={14} /> Workflow</div><p className="subtitle">1. Detect provider<br />2. Create persistent session<br />3. Open meeting externally<br />4. Load Live Copilot with the session and answer settings<br />5. Use the always-on-top overlay for generated answers</p></div>
    </aside></div>
    <button className="secondary" style={{ marginTop: 20 }} onClick={() => { window.location.href = "/"; }}><ArrowLeft size={16} /> Back to workspace</button>
  </main>;
}
