export {};
declare global {
  interface GenQuantaaDesktopBridge {
    publishCopilotUpdate?: (payload: unknown) => Promise<boolean>;
    detectMeetingProvider?: (url: string) => Promise<{ id: string; name: string } | null>;
    getMeetingProviders?: () => Promise<Array<{ id: string; name: string }>>;
    startMeetingMonitor?: (payload: { meetingUrl: string; title?: string; autoAnswer?: boolean; answerMode?: string; openMeeting?: boolean }) => Promise<unknown>;
    stopMeetingMonitor?: () => Promise<unknown>; getMeetingState?: () => Promise<unknown>; onMeetingState?: (callback: (state: unknown) => void) => () => void;
    getScreenContextSources?: () => Promise<unknown>; startScreenContext?: (sourceId: string) => Promise<unknown>; analyzeScreenContext?: () => Promise<unknown>;
    startContinuousScreenContext?: (intervalMs?: number) => Promise<unknown>; stopContinuousScreenContext?: () => Promise<unknown>;
    stopScreenContext?: () => Promise<unknown>; getScreenContextState?: () => Promise<unknown>; onScreenContextState?: (callback: (state: unknown) => void) => () => void;
    onCopilotUpdate?: (callback: (payload: unknown) => void) => () => void;
  }
  interface Window { genquantaa?: GenQuantaaDesktopBridge; }
}
