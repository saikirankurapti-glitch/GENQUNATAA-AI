const { shell } = require('electron');

const PROVIDERS = [
  { id: 'google-meet', name: 'Google Meet', hosts: ['meet.google.com'] },
  { id: 'microsoft-teams', name: 'Microsoft Teams', hosts: ['teams.microsoft.com', 'teams.live.com'] },
  { id: 'zoom', name: 'Zoom', hosts: ['zoom.us', 'zoom.com'] },
  { id: 'webex', name: 'Webex', hosts: ['webex.com'] },
  { id: 'hackerrank', name: 'HackerRank', hosts: ['hackerrank.com'] },
  { id: 'leetcode', name: 'LeetCode', hosts: ['leetcode.com'] },
];

function detectMeetingProvider(rawUrl) {
  try {
    const url = new URL(rawUrl);
    if (!['http:', 'https:'].includes(url.protocol)) return null;
    const hostname = url.hostname.toLowerCase().replace(/^www\./, '');
    return PROVIDERS.find((provider) => provider.hosts.some((host) => hostname === host || hostname.endsWith(`.${host}`))) || null;
  } catch {
    return null;
  }
}

function sanitizeTitle(value) {
  return String(value || '').trim().replace(/[\r\n]+/g, ' ').slice(0, 120);
}

class MeetingOrchestrator {
  constructor({ mainWindow, webUrl, apiUrl, authCookieProvider, onAuthRequired, onState }) {
    this.mainWindow = mainWindow;
    this.webUrl = webUrl;
    this.apiUrl = apiUrl;
    this.authCookieProvider = authCookieProvider;
    this.onAuthRequired = onAuthRequired;
    this.onState = onState;
    this.timer = null;
    this.state = { active: false, provider: null, provider_name: null, meeting_url: null, session_id: null, title: null };
  }

  emit(extra = {}) {
    this.state = { ...this.state, ...extra };
    this.onState?.(this.state);
  }

  async authenticatedFetch(url, options = {}) {
    const cookie = await this.authCookieProvider?.();
    if (!cookie) {
      this.emit({ active: false, status: 'auth_required', error: 'Please sign in to GenQuantaa AI before starting a meeting session.' });
      await this.onAuthRequired?.();
      throw new Error('Authentication required');
    }
    const headers = { ...(options.headers || {}), Cookie: cookie };
    return fetch(url, { ...options, headers });
  }

  async start({ meetingUrl, title, answerMode = 'concise', autoAnswer = true, openMeeting = true }) {
    const provider = detectMeetingProvider(meetingUrl);
    if (!provider) throw new Error('Unsupported meeting/interview URL. Supported: Google Meet, Microsoft Teams, Zoom, Webex, HackerRank, and LeetCode.');
    if (this.state.active) await this.stop(false);

    const sessionTitle = sanitizeTitle(title) || `${provider.name} interview`;
    this.emit({ active: true, provider: provider.id, provider_name: provider.name, meeting_url: meetingUrl, session_id: null, title: sessionTitle, status: 'creating_session' });

    try {
      const response = await this.authenticatedFetch(`${this.apiUrl}/api/v1/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: sessionTitle, mode: 'copilot' }),
      });
      const data = await response.json().catch(() => ({}));
      if (response.status === 401) {
        await this.stop(false);
        this.emit({ active: false, status: 'auth_required', error: 'Your GenQuantaa session has expired. Please sign in again.' });
        await this.onAuthRequired?.();
        return this.state;
      }
      if (!response.ok) throw new Error(data.detail || `Session creation failed (${response.status})`);

      this.emit({ session_id: data.id, status: 'session_ready' });
      const liveUrl = `${this.webUrl}/live?session=${encodeURIComponent(data.id)}&provider=${encodeURIComponent(provider.id)}&auto_answer=${autoAnswer ? '1' : '0'}&answer_mode=${encodeURIComponent(answerMode)}`;
      await this.mainWindow.loadURL(liveUrl);
      if (openMeeting) await shell.openExternal(meetingUrl);
      this.emit({ status: 'running' });
      this.timer = setInterval(() => this.emit({ status: 'running' }), 5000);
      return this.state;
    } catch (error) {
      this.emit({ active: false, status: 'error', error: error instanceof Error ? error.message : 'Meeting orchestration failed' });
      throw error;
    }
  }

  async stop(emitState = true) {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    const previous = { session_id: this.state.session_id, provider: this.state.provider, provider_name: this.state.provider_name };
    this.state = { active: false, provider: null, provider_name: null, meeting_url: null, session_id: null, title: null, status: 'stopped', previous_session_id: previous.session_id };
    if (emitState) this.onState?.(this.state);
    return this.state;
  }

  getState() {
    return this.state;
  }
}

module.exports = { MeetingOrchestrator, PROVIDERS, detectMeetingProvider };
