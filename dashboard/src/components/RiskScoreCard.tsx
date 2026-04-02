"use client";

import clsx from "clsx";
import type { ScanResponse, RiskLevel } from "@/lib/types";
import { ShieldAlert, ShieldCheck, ShieldOff, Shield } from "lucide-react";

interface Props {
  result: ScanResponse;
}

const LEVEL_CONFIG: Record<
  RiskLevel,
  { color: string; bg: string; border: string; Icon: React.ElementType; label: string }
> = {
  low: {
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    Icon: ShieldCheck,
    label: "LOW RISK",
  },
  medium: {
    color: "text-amber-400",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    Icon: Shield,
    label: "MEDIUM RISK",
  },
  high: {
    color: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    Icon: ShieldAlert,
    label: "HIGH RISK",
  },
  critical: {
    color: "text-purple-400",
    bg: "bg-purple-500/10",
    border: "border-purple-500/30",
    Icon: ShieldOff,
    label: "CRITICAL",
  },
  unknown: {
    color: "text-slate-400",
    bg: "bg-slate-500/10",
    border: "border-slate-500/30",
    Icon: Shield,
    label: "UNKNOWN",
  },
};

function ScoreGauge({ score }: { score: number }) {
  // Score gauge using SVG arc
  const r = 56;
  const cx = 70;
  const cy = 70;
  const circumference = Math.PI * r; // half circle
  const dashOffset = circumference * (1 - score / 100);

  const color =
    score >= 70
      ? "#a855f7"
      : score >= 40
      ? "#ef4444"
      : score >= 15
      ? "#f59e0b"
      : "#10b981";

  return (
    <svg viewBox="0 0 140 90" className="w-36 h-auto">
      {/* Track */}
      <path
        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none"
        stroke="#334155"
        strokeWidth="10"
        strokeLinecap="round"
      />
      {/* Fill */}
      <path
        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none"
        stroke={color}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={dashOffset}
        style={{ transition: "stroke-dashoffset 0.6s ease" }}
      />
      <text
        x={cx}
        y={cy - 4}
        textAnchor="middle"
        className="fill-slate-100"
        fontSize="22"
        fontWeight="bold"
      >
        {score.toFixed(0)}
      </text>
      <text
        x={cx}
        y={cy + 14}
        textAnchor="middle"
        className="fill-slate-400"
        fontSize="9"
      >
        / 100
      </text>
    </svg>
  );
}

export default function RiskScoreCard({ result }: Props) {
  const level = (result.risk_level as RiskLevel) ?? "unknown";
  const cfg = LEVEL_CONFIG[level] ?? LEVEL_CONFIG.unknown;
  const { Icon } = cfg;

  return (
    <div
      className={clsx(
        "rounded-2xl border p-5 flex flex-col gap-4",
        cfg.bg,
        cfg.border
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2">
        <Icon size={18} className={cfg.color} />
        <span className={clsx("text-xs font-bold tracking-widest", cfg.color)}>
          {cfg.label}
        </span>
      </div>

      {/* Score gauge + meta */}
      <div className="flex items-center gap-6">
        <ScoreGauge score={result.risk_score} />
        <div className="flex flex-col gap-1 text-sm">
          {result.address && (
            <span className="text-slate-400 font-mono text-xs truncate max-w-[160px]">
              {result.address}
            </span>
          )}
          <span>
            <span className="text-slate-400">Vulns:</span>{" "}
            <span className="font-semibold text-slate-200">
              {result.vulnerability_count}
            </span>
          </span>
          <span>
            <span className="text-slate-400">Proxy:</span>{" "}
            <span className={result.profile.is_proxy ? "text-amber-400" : "text-slate-400"}>
              {result.profile.is_proxy ? "Yes" : "No"}
            </span>
          </span>
          <span>
            <span className="text-slate-400">Mint:</span>{" "}
            <span className={result.profile.has_mint ? "text-amber-400" : "text-slate-400"}>
              {result.profile.has_mint ? "Yes" : "No"}
            </span>
          </span>
          <span>
            <span className="text-slate-400">Ownership:</span>{" "}
            <span className={result.profile.has_ownership ? "text-amber-400" : "text-slate-400"}>
              {result.profile.has_ownership ? "Yes" : "No"}
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}
