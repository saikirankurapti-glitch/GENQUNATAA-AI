"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, Monitor, RefreshCw, Square, Target } from "lucide-react";

type Source = { id: string; name: string; display_id?: string | null; thumbnail?: string | null };
type State = { active?: boolean; selected_source?: Source | null; sources?: Source[]; last_capture_at?: string | null; status?: string; error?: string };

export default function ScreenContextPage() {
  const [state, setState] = useState<State>({ status: "idle", sources: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function refresh() { setLoading(true); setError(""); try { const result = await window.genquantaa?.getScreenContextSources?.() as State | undefined; if (result) setState(result); } catch (e) { setError(e instanceof Error ? e.message : "Could not list screen sources."); } finally { setLoading(false); } }
  useEffect(() => { window.genquantaa?.getScreenContextState?.().then((result) => { if (result) setState(result as State); }); const unsubscribe = window.genquantaa?.onScreenContextState?.((incoming) => setState(incoming as State)); void refresh(); return () => unsubscribe?.(); }, []);

  async function selectSource(id: string) { setLoading(true); setError(""); try { const result = await window.genquantaa?.startScreenContext?.(id) as State | undefined; if (result) { setState(result); if (result.status === "error") setError(result.error || "Could not select source."); } } catch (e) { setError(e instanceof Error ? e.message : "Could not start screen context."); } finally { setLoading(false); } }
  async function stop() { const result = await window.genquantaa?.stopScreenContext?.() as State | undefined; if (result) setState(result); }

  const sources = state.sources || [];
  return <main className="main">
    <div className="top"><div><div className="eyebrow">Screen Context Intelligence · Phase 1</div><h1 className="title">Screen Context</h1><div className="subtitle">Choose a specific window or display for future OCR, coding-context, and visual interview intelligence.</div></div><span className="pill"><Monitor size={14} /> {state.active ? "Capture ready" : "Not capturing"}</span></div>
    {error && <div className="card" style={{ marginBottom: 18 }}>{error}</div>}
    <div className="grid"><section>
      <div className="card hero"><div><div className="eyebrow"><Target size={14} /> Source selection</div><h2>Select what GenQuantaa is allowed to use as visual context.</h2><p className="subtitle">Phase 1 only establishes a secure, user-selected capture source. It does not run OCR or send screenshots to an AI provider yet.</p></div><div className="actions" style={{ marginTop: 18 }}><button className="secondary" onClick={refresh} disabled={loading}><RefreshCw size={16} /> {loading ? "Refreshing…" : "Refresh sources"}</button>{state.active && <button className="secondary" onClick={stop}><Square size={16} /> Stop context</button>}</div></div>
      <div className="card" style={{ marginTop: 20 }}><div className="eyebrow">Available windows & displays</div>{sources.length === 0 ? <p className="muted">No capture sources found. Use the desktop app and refresh.</p> : <div className="list">{sources.map((source) => <div className="row" key={source.id} style={{ gap: 14, alignItems: "center" }}><div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1 }}>{source.thumbnail ? <img src={source.thumbnail} alt="" width={96} height={54} style={{ objectFit: "cover", borderRadius: 8 }} /> : <Monitor size={20} />}<span><strong>{source.name}</strong><br /><small className="muted">{source.display_id ? `Display ${source.display_id}` : "Window"}</small></span></div><button className={state.selected_source?.id === source.id ? "primary" : "secondary"} onClick={() => selectSource(source.id)} disabled={loading}>{state.selected_source?.id === source.id ? "Selected" : "Use source"}</button></div>)}</div>}</div>
    </section><aside>
      <div className="card"><div className="eyebrow">Context status</div><div className="list"><div className="row"><span>Permission</span><b>User selected</b></div><div className="row"><span>Capture state</span><b>{state.active ? "Ready" : "Stopped"}</b></div><div className="row"><span>Selected source</span><b>{state.selected_source?.name || "—"}</b></div><div className="row"><span>Last selection</span><b>{state.last_capture_at ? new Date(state.last_capture_at).toLocaleTimeString() : "—"}</b></div></div></div>
      <div className="card" style={{ marginTop: 20 }}><div className="eyebrow">Phase 1 boundary</div><p className="subtitle">✓ Enumerate windows and displays<br />✓ Let the user choose one source<br />✓ Keep the bridge context-isolated<br />✓ Track capture state<br />○ OCR extraction — Phase 2<br />○ Context classification — Phase 2<br />○ Coding integration — Phase 3</p></div>
    </aside></div>
    <button className="secondary" style={{ marginTop: 20 }} onClick={() => { window.location.href = "/"; }}><ArrowLeft size={16} /> Back to workspace</button>
  </main>;
}
