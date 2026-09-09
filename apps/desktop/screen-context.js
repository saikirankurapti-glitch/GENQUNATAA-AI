const { desktopCapturer, screen } = require('electron');

function normalizeSource(source) {
  return { id: source.id, name: String(source.name || 'Untitled').slice(0, 200), display_id: source.display_id || null, thumbnail: source.thumbnail ? source.thumbnail.toDataURL() : null };
}

class ScreenContextService {
  constructor({ onState }) {
    this.onState = onState;
    this.active = false;
    this.selectedSource = null;
    this.sources = [];
    this.lastCapture = null;
  }

  emit(extra = {}) {
    const state = { active: this.active, selected_source: this.selectedSource, sources: this.sources, last_capture_at: this.lastCapture, ...extra };
    this.onState?.(state);
    return state;
  }

  async listSources() {
    const sources = await desktopCapturer.getSources({ types: ['window', 'screen'], thumbnailSize: { width: 320, height: 180 }, fetchWindowIcons: false });
    this.sources = sources.map(normalizeSource);
    return this.emit();
  }

  async start(sourceId) {
    const sources = await desktopCapturer.getSources({ types: ['window', 'screen'], thumbnailSize: { width: 320, height: 180 }, fetchWindowIcons: false });
    const selected = sources.find((source) => source.id === sourceId);
    if (!selected) throw new Error('Screen or window source not found. Refresh the available sources and try again.');
    this.sources = sources.map(normalizeSource);
    this.selectedSource = normalizeSource(selected);
    this.active = true;
    this.lastCapture = new Date().toISOString();
    return this.emit({ status: 'ready' });
  }

  stop() {
    this.active = false;
    this.lastCapture = null;
    return this.emit({ status: 'stopped' });
  }

  getState() { return this.emit(); }
}

module.exports = { ScreenContextService };
