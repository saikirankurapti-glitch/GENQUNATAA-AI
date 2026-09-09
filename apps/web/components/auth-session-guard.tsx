"use client";

import { useCallback, useEffect, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const AUTH_PATH = "/auth";
const CHECK_INTERVAL_MS = 30_000;

function redirectToAuth() {
  if (typeof window === "undefined" || window.location.pathname === AUTH_PATH) return;
  const next = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  const target = `${AUTH_PATH}?next=${encodeURIComponent(next || "/")}`;
  window.location.replace(target);
}

export default function AuthSessionGuard() {
  const redirecting = useRef(false);

  const checkSession = useCallback(async () => {
    if (typeof window === "undefined" || window.location.pathname === AUTH_PATH || redirecting.current) return;
    try {
      const response = await fetch(`${API}/api/v1/auth/me`, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
      });
      if (response.status === 401) {
        redirecting.current = true;
        redirectToAuth();
      }
    } catch {
      // Do not redirect when the API is temporarily unavailable. A network
      // outage is not evidence that the user's session has expired.
    }
  }, []);

  useEffect(() => {
    void checkSession();

    const interval = window.setInterval(() => void checkSession(), CHECK_INTERVAL_MS);
    const onFocus = () => void checkSession();
    const onVisibility = () => {
      if (document.visibilityState === "visible") void checkSession();
    };

    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [checkSession]);

  return null;
}
