"use client";

import { useEffect, useRef, useState } from "react";
import type { ThreatAlert, RiskLevel } from "@/lib/types";
import { AlertTriangle, Radio } from "lucide-react";
import clsx from "clsx";

const WS_URL =
  (typeof window !== "undefined"
    ? process.env.NEXT_PUBLIC_WS_URL
    : undefined) ?? "ws://localhost:8000";

const RECONNECT_DELAY_MS = 5000;

const LEVEL_COLOR: Record<string, string> = {
  critical: "border-l-purple-500 bg-purple-500/5",
  high: "border-l-red-500 bg-red-500/5",
  medium: "border-l-amber-500 bg-amber-500/5",
  low: "border-l-emerald-500 bg-emerald-500/5",
  unknown: "border-l-slate-500 bg-slate-500/5",
};

const SCORE_COLOR: Record<string, string> = {
  critical: "text-purple-400",
  high: "text-red-400",
  medium: "text-amber-400",
  low: "text-emerald-400",
  unknown: "text-slate-400",
};

export default function LiveThreatFeed() {
  const [alerts, setAlerts] = useState<ThreatAlert[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      ws = new WebSocket(`${WS_URL}/api/v1/realtime/threats`);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        // Reconnect after RECONNECT_DELAY_MS
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };
      ws.onerror = () => ws.close();

      ws.onmessage = (ev) => {
        try {
          const msg: ThreatAlert = JSON.parse(ev.data as string);
          if (msg.type === "ping") return;
          setAlerts((prev) => [msg, ...prev].slice(0, 50));
        } catch {
          // ignore malformed
        }
      };
    }

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);

  return (
    <div className="rounded-2xl bg-slate-800 border border-slate-700 flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700">
        <Radio size={14} className="text-sky-400" />
        <span className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
          Live Threat Feed
        </span>
        <span
          className={clsx(
            "ml-auto flex items-center gap-1.5 text-xs",
            connected ? "text-emerald-400" : "text-slate-500"
          )}
        >
          <span
            className={clsx(
              "w-2 h-2 rounded-full live-dot",
              connected ? "bg-emerald-400" : "bg-slate-500"
            )}
          />
          {connected ? "Connected" : "Connecting…"}
        </span>
      </div>

      {/* Alerts */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
        {alerts.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-slate-600">
            <AlertTriangle size={28} />
            <p className="text-sm">Waiting for contract deployments…</p>
            <p className="text-xs text-slate-700">
              Alerts appear when new contracts are detected on-chain
            </p>
          </div>
        )}
        {alerts.map((alert, i) => {
          const level = (alert.risk_level ?? "unknown") as RiskLevel;
          return (
            <div
              key={i}
              className={clsx(
                "rounded-lg border-l-2 px-3 py-2.5 text-xs",
                LEVEL_COLOR[level] ?? LEVEL_COLOR.unknown
              )}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-slate-300 truncate max-w-[180px]">
                  {alert.address ?? "Unknown"}
                </span>
                <span
                  className={clsx(
                    "font-bold",
                    SCORE_COLOR[level] ?? SCORE_COLOR.unknown
                  )}
                >
                  {alert.risk_score?.toFixed(0) ?? "?"} / 100
                </span>
              </div>
              {alert.reasons && alert.reasons.length > 0 && (
                <ul className="text-slate-500 space-y-0.5">
                  {alert.reasons.slice(0, 3).map((r, j) => (
                    <li key={j}>• {r}</li>
                  ))}
                </ul>
              )}
              {alert.creator && (
                <p className="mt-1 text-slate-600 font-mono">
                  Creator: {alert.creator.slice(0, 10)}…
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
