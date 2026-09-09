"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, Brain, CheckCircle2, Code2, FileText, Monitor, RefreshCw, Square, Target } from "lucide-react";

type Source = { id: string; name: string; display_id?: string | null; thumbnail?: string | null };
type Analysis = { summary?: string; visible_text?: string; code?: string; language?: string | null; context_type?: string; question?: string | null; confidence?: number; actionable_context?: string };
type State = { active?: boolean; selected_source?: Source | null; sources?: Source[]; last_capture_at?: string | null; last_analysis_at?: string | null; analysis?: Analysis | null; status?: string; error?: string };

export default function ScreenContextPage() {
  const [state, setState] = useState<State>({ status: "idle", sources: [] });
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  async function refresh() { setLoading(true); setError(""); try { const result = await window.genquantaa?.getScreenContextSources?.() as State | undefined; if (result) setState(result); } catch (e) { setError(e instanceof Error ? e.message : "Could not list screen sources."); } finally { setLoading(false); } }
  useEffect(() => { window.genquantaa?.getScreenContextState?.().then((result) => { if (result) setState(result as State); }); const unsubscribe = window.genquantaa?.onScreenContextState?.((incoming) => setState(incoming as State)); void refresh(); return () => unsubscribe?.(); }, []);

  async function selectSource(id: string) { setLoading(true); setError(""); try { const result = await window.genquantaa?.startScreenContext?.(id) as State | undefined; if (result) { setState(result); if (result.status === "error") setError(result.error || "Could not select source."); } } catch (e) { setError(e instanceof Error ? e.message : "Could not start screen context."); } finally { setLoading(false); } }
  async function analyze() { setAnalyzing(true); setError(""); try { const result = await window.genquantaa?.analyzeScreenContext?.() as State | undefined; if (result) { setState(result); if (result.status === "error") setError(result.error || "Visual analysis failed."); } } catch (e) { setError(e instanceof Error ? e.message : "Visual analysis failed."); } finally { setAnalyzing(false); } }
  async function stop() { const result = await window.genquantaa?.stopScreenContext?.() as State | undefined; if (result) setState(result); }

  const sources = state.sources || [];
  const analysis = state.analysis;
  const pct = Math.round((analysis?.confidence || 0) * 100);
  return <main className="main">
    <div className="top"><div><div className="eyebrow">Screen Context Intelligence · Phase 2</div><h1 className="title">Screen Context</h1><div className="subtitle">Capture one explicitly selected window or display and turn its visible content into structured AI context.</div></div><span className="pill"><Monitor size={14} /> {state.active ? "Capture ready" : "Not capturing"}</span></div>
    {error && <div className="card" style={{ marginBottom: 18 }}>{error}</div>}
    <div className="grid"><section>
      <div className="card hero"><div><div className="eyebrow"><Target size={14} /> Source selection</div><h2>Select what GenQuantaa is allowed to analyze.</h2><p className="subtitle">Screenshots are captured only after you select a source and request analysis. Image bytes are sent to the backend for Gemini Vision analysis and are not persisted by the visual endpoint.</p></div><div className="actions" style={{ marginTop: 18 }}><button className="secondary" onClick={refresh} disabled={loading || analyzing}><RefreshCw size={16} /> {loading ? "Refreshing…" : "Refresh sources"}</button>{state.active && <button className="primary" onClick={analyze} disabled={analyzing}><Brain size={16} /> {analyzing ? "Analyzing…" : "Analyze selected screen"}</button>}{state.active && <button className="secondary" onClick={stop} disabled={analyzing}><Square size={16} /> Stop context</button>}</div></div>
      <div className="card" style={{ marginTop: 20 }}><div className="eyebrow">Available windows & displays</div>{sources.length === 0 ? <p className="muted">No capture sources found. Use the desktop app and refresh.</p> : <div className="list">{sources.map((source) => <div className="row" key={source.id} style={{ gap: 14, alignItems: "center" }}><div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1 }}>{source.thumbnail ? <img src={source.thumbnail} alt="" width={96} height={54} style={{ objectFit: "cover", borderRadius: 8 }} /> : <Monitor size={20} />}<span><strong>{source.name}</strong><br /><small className="muted">{source.display_id ? `Display ${source.display_id}` : "Window"}</small></span></div><button className={state.selected_source?.id === source.id ? "primary" : "secondary"} onClick={() => selectSource(source.id)} disabled={loading || analyzing}>{state.selected_source?.id === source.id ? "Selected" : "Use source"}</button></div>)}</div>}</div>
      {analysis && <div className="card" style={{ marginTop: 20 }}><div className="eyebrow"><Brain size={14} /> Gemini Vision result</div><h2>{analysis.summary || "Visual context analyzed"}</h2><div className="list" style={{ marginTop: 14 }}><div className="row"><span>Context type</span><b>{analysis.context_type || "unknown"}</b></div><div className="row"><span>Confidence</span><b>{pct}%</b></div><div className="row"><span>Language</span><b>{analysis.language || "—"}</b></div></div>{analysis.question && <div style={{ marginTop: 18 }}><div className="eyebrow"><FileText size={14} /> Detected question</div><p>{analysis.question}</p></div>}{analysis.visible_text && <div style={{ marginTop: 18 }}><div className="eyebrow">Visible text</div><pre style={{ whiteSpace: "pre-wrap", overflowX: "auto" }}>{analysis.visible_text}</pre></div>}{analysis.code && <div style={{ marginTop: 18 }}><div className="eyebrow"><Code2 size={14} /> Detected code</div><pre style={{ whiteSpace: "pre-wrap", overflowX: "auto" }}>{analysis.code}</pre></div>}{analysis.actionable_context && <div style={{ marginTop: 18 }}><div className="eyebrow"><CheckCircle2 size={14} /> Copilot context</div><p className="subtitle">{analysis.actionable_context}</p></div>}</div>}
    </section><aside>
      <div className="card"><div className="eyebrow">Context status</div><div className="list"><div className="row"><span>Permission</span><b>User selected</b></div><div className="row"><span>Capture state</span><b>{state.active ? "Ready" : "Stopped"}</b></div><div className="row"><span>Selected source</span><b>{state.selected_source?.name || "—"}</b></div><div className="row"><span>Last analysis</span><b>{state.last_analysis_at ? new Date(state.last_analysis_at).toLocaleTimeString() : "—"}</b></div></div></div>
      <div className="card" style={{ marginTop: 20 }}><div className="eyebrow">Phase 2 boundary</div><p className="subtitle">✓ Enumerate windows and displays<br />✓ User-selected source capture<br />✓ Gemini Vision extraction<br />✓ OCR-style visible text extraction<br />✓ Code & language detection<br />✓ Question/context classification<br />✓ Confidence + actionable context<br />○ Continuous capture — later phase<br />○ Automatic Copilot fusion — Phase 3</p></div>
    </aside></div>
    <button className="secondary" style={{ marginTop: 20 }} onClick={() => { window.location.href = "/"; }}><ArrowLeft size={16} /> Back to workspace</button>
  </main>;
}
