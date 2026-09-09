const { desktopCapturer } = require('electron');

const DEFAULT_INTERVAL_MS = 8000;
const MIN_INTERVAL_MS = 5000;
const MAX_INTERVAL_MS = 60000;

function normalizeSource(source) {
  return {
    id: source.id,
    name: String(source.name || 'Untitled').slice(0, 200),
    display_id: source.display_id || null,
    thumbnail: source.thumbnail ? source.thumbnail.toDataURL() : null
  };
}

class ScreenContextService {
  constructor({ onState, apiUrl }) {
    this.onState = onState; this.apiUrl = apiUrl; this.active = false; this.selectedSource = null; this.sources = [];
    this.lastCapture = null; this.lastAnalysis = null; this.continuous = false; this.intervalMs = DEFAULT_INTERVAL_MS; this.timer = null; this.analyzing = false;
  }
  emit(extra = {}) {
    const state = { active: this.active, selected_source: this.selectedSource, sources: this.sources, last_capture_at: this.lastCapture,
      last_analysis_at: this.lastAnalysis?.analyzed_at || null, analysis: this.lastAnalysis?.analysis || null, continuous: this.continuous,
      interval_ms: this.intervalMs, analyzing: this.analyzing, ...extra };
    this.onState?.(state); return state;
  }
  async listSources() {
    const sources = await desktopCapturer.getSources({ types: ['window', 'screen'], thumbnailSize: { width: 320, height: 180 }, fetchWindowIcons: false });
    this.sources = sources.map(normalizeSource); return this.emit();
  }
  async start(sourceId) {
    this.stopContinuous();
    const sources = await desktopCapturer.getSources({ types: ['window', 'screen'], thumbnailSize: { width: 320, height: 180 }, fetchWindowIcons: false });
    const selected = sources.find((source) => source.id === sourceId);
    if (!selected) throw new Error('Screen or window source not found. Refresh the available sources and try again.');
    this.sources = sources.map(normalizeSource); this.selectedSource = normalizeSource(selected); this.active = true;
    this.lastCapture = new Date().toISOString(); this.lastAnalysis = null; return this.emit({ status: 'ready' });
  }
  async analyze() {
    if (!this.active || !this.selectedSource) throw new Error('Select a screen or window before analyzing visual context.');
    if (this.analyzing) return this.emit({ status: 'analyzing' });
    this.analyzing = true; this.emit({ status: 'capturing' });
    try {
      const sources = await desktopCapturer.getSources({ types: ['window', 'screen'], thumbnailSize: { width: 1280, height: 720 }, fetchWindowIcons: false });
      const selected = sources.find((source) => source.id === this.selectedSource.id);
      if (!selected) throw new Error('The selected source is no longer available. Refresh and select it again.');
      const image = selected.thumbnail?.toPNG(); if (!image || image.length === 0) throw new Error('Could not capture the selected source.');
      const form = new FormData(); form.append('file', new Blob([image], { type: 'image/png' }), 'screen-context.png');
      const response = await fetch(`${this.apiUrl}/api/v1/visual/analyze`, { method: 'POST', body: form });
      const payload = await response.json().catch(() => ({})); if (!response.ok) throw new Error(payload.detail || `Visual analysis failed (${response.status})`);
      this.lastCapture = new Date().toISOString(); this.lastAnalysis = { analyzed_at: this.lastCapture, analysis: payload.analysis }; return this.emit({ status: 'analyzed' });
    } finally { this.analyzing = false; this.emit(); }
  }
  startContinuous(intervalMs = DEFAULT_INTERVAL_MS) {
    if (!this.active || !this.selectedSource) throw new Error('Select a screen or window before enabling continuous context.');
    const requested = Number(intervalMs); this.intervalMs = Number.isFinite(requested) ? Math.max(MIN_INTERVAL_MS, Math.min(MAX_INTERVAL_MS, Math.round(requested))) : DEFAULT_INTERVAL_MS;
    this.stopContinuous(); this.continuous = true;
    this.timer = setInterval(() => { if (!this.active || !this.continuous || this.analyzing) return; void this.analyze().catch((error) => this.emit({ status: 'error', error: error instanceof Error ? error.message : 'Continuous visual analysis failed' })); }, this.intervalMs);
    return this.emit({ status: 'continuous' });
  }
  stopContinuous() { if (this.timer) clearInterval(this.timer); this.timer = null; this.continuous = false; }
  stop() { this.stopContinuous(); this.active = false; this.lastCapture = null; this.lastAnalysis = null; this.analyzing = false; return this.emit({ status: 'stopped' }); }
  getState() { return this.emit(); }
}
module.exports = { ScreenContextService, DEFAULT_INTERVAL_MS, MIN_INTERVAL_MS, MAX_INTERVAL_MS };
