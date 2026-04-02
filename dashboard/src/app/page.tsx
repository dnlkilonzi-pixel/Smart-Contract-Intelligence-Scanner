"use client";

import { useState } from "react";
import { Shield, Github, ExternalLink } from "lucide-react";
import ContractSearch from "@/components/ContractSearch";
import RiskScoreCard from "@/components/RiskScoreCard";
import VulnerabilityBreakdown from "@/components/VulnerabilityBreakdown";
import LiveThreatFeed from "@/components/LiveThreatFeed";
import WalletGraph from "@/components/WalletGraph";
import type { ScanResponse } from "@/lib/types";

export default function DashboardPage() {
  const [scanResult, setScanResult] = useState<ScanResponse | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [walletAddress, setWalletAddress] = useState<string>("");
  const [graphAddress, setGraphAddress] = useState<string>("");

  function handleResult(result: ScanResponse) {
    setScanResult(result);
    setScanError(null);
    // If result has an address, auto-populate the wallet graph
    if (result.address) {
      const creator = result.profile.creator_address;
      if (creator) setGraphAddress(creator);
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-900">
      {/* ── Navbar ── */}
      <nav className="border-b border-slate-800 px-6 py-3 flex items-center gap-3">
        <Shield size={20} className="text-sky-500" />
        <span className="font-bold text-slate-100 tracking-tight">
          Smart Contract Intelligence Scanner
        </span>
        <span className="ml-1 text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded">
          v1.0
        </span>
        <a
          href="/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto flex items-center gap-1 text-xs text-slate-400 hover:text-sky-400 transition-colors"
        >
          API Docs <ExternalLink size={11} />
        </a>
      </nav>

      {/* ── Main content ── */}
      <main className="flex-1 p-6 flex flex-col gap-6">
        {/* Search bar */}
        <section>
          <ContractSearch onResult={handleResult} onError={setScanError} />
          {scanError && (
            <p className="mt-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              ⚠ {scanError}
            </p>
          )}
        </section>

        {/* Top row: Risk score card + Live threat feed */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: scan result */}
          <div className="lg:col-span-2 flex flex-col gap-4">
            {scanResult ? (
              <>
                <RiskScoreCard result={scanResult} />
                <VulnerabilityBreakdown result={scanResult} />
              </>
            ) : (
              <EmptyState />
            )}
          </div>

          {/* Right: live feed */}
          <div className="h-[520px]">
            <LiveThreatFeed />
          </div>
        </section>

        {/* Wallet Graph section */}
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
            Wallet Relationship Graph
          </h2>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={walletAddress}
              onChange={(e) => setWalletAddress(e.target.value)}
              placeholder="Enter wallet address (0x…) to visualise relationships"
              className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 outline-none focus:border-sky-500 transition-colors"
            />
            <button
              onClick={() => setGraphAddress(walletAddress)}
              disabled={!walletAddress.startsWith("0x")}
              className="bg-sky-600 hover:bg-sky-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2.5 rounded-xl transition-colors"
            >
              Visualise
            </button>
          </div>
          {graphAddress && <WalletGraph address={graphAddress} />}
        </section>
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-slate-800 px-6 py-3 flex items-center text-xs text-slate-600">
        <span>Smart Contract Intelligence Scanner &copy; {new Date().getFullYear()}</span>
        <a
          href="https://github.com/dnlkilonzi-pixel/Smart-Contract-Intelligence-Scanner"
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto flex items-center gap-1 hover:text-slate-400 transition-colors"
        >
          <Github size={12} /> GitHub
        </a>
      </footer>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-2xl bg-slate-800/50 border border-slate-700/50 border-dashed p-10 flex flex-col items-center gap-3 text-center">
      <Shield size={36} className="text-slate-700" />
      <p className="text-slate-400 font-medium">No scan results yet</p>
      <p className="text-slate-600 text-sm max-w-sm">
        Enter a contract address or paste Solidity source code in the search bar
        above to run a full security scan.
      </p>
    </div>
  );
}
