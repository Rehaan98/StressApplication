"use client";

import { useEffect, useRef } from "react";

const DATA_EVENT = "stressai:data-updated";
const STORAGE_KEY = "stressai:data-updated-at";
const MIN_NOTIFY_GAP_MS = 1200;

let lastNotifyAt = 0;

/**
 * Tell every mounted page (and other browser tabs) that new assessment,
 * facial, voice, or multimodal data has been saved, so they re-fetch.
 */
export function notifyDataUpdated(force = false): void {
  if (typeof window === "undefined") return;
  const now = Date.now();
  if (!force && now - lastNotifyAt < MIN_NOTIFY_GAP_MS) return;
  lastNotifyAt = now;
  try {
    window.localStorage.setItem(STORAGE_KEY, String(now));
  } catch {
    // Private mode / storage disabled — the same-tab event still works.
  }
  window.dispatchEvent(new CustomEvent(DATA_EVENT, { detail: { at: now } }));
}

interface LiveDataOptions {
  intervalMs?: number;
  enabled?: boolean;
}

/**
 * Keeps a page's data fresh: refreshes when new data is saved, when the tab
 * regains focus/visibility, when another tab syncs, and optionally on a poll.
 * The first load is left to the component; this only handles follow-up loads.
 */
export function useLiveData(
  refresh: () => void | Promise<void>,
  options: LiveDataOptions = {}
): void {
  const refreshRef = useRef(refresh);
  const { intervalMs, enabled = true } = options;

  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    let cancelled = false;
    const run = () => {
      if (!cancelled) void refreshRef.current();
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") run();
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === STORAGE_KEY) run();
    };

    window.addEventListener("focus", run);
    window.addEventListener("storage", onStorage);
    window.addEventListener(DATA_EVENT, run);
    document.addEventListener("visibilitychange", onVisibility);

    const timer = intervalMs ? window.setInterval(run, intervalMs) : undefined;

    return () => {
      cancelled = true;
      window.removeEventListener("focus", run);
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(DATA_EVENT, run);
      document.removeEventListener("visibilitychange", onVisibility);
      if (timer) window.clearInterval(timer);
    };
  }, [enabled, intervalMs]);
}
