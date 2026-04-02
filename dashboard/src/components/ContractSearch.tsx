"use client";

import { useState } from "react";
import { Search, Loader2 } from "lucide-react";
import type { ScanResponse } from "@/lib/types";
import { scanContract } from "@/lib/api";

interface Props {
  onResult: (result: ScanResponse) => void;
  onError: (msg: string) => void;
}

export default function ContractSearch({ onResult, onError }: Props) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const isAddress = input.startsWith("0x") && input.length === 42;

  async function handleScan(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    setLoading(true);
    try {
      const req = isAddress
        ? { address: input.trim() }
        : { source_code: input.trim() };
      const result = await scanContract(req);
      onResult(result);
    } catch (err: unknown) {
      onError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleScan}
      className="flex items-center gap-2 bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 shadow-lg"
    >
      <Search size={18} className="text-slate-400 shrink-0" />
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Enter contract address (0x…) or paste Solidity source code"
        className="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-500 outline-none"
        disabled={loading}
      />
      <button
        type="submit"
        disabled={loading || !input.trim()}
        className="flex items-center gap-1.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors"
      >
        {loading ? (
          <>
            <Loader2 size={14} className="animate-spin" />
            Scanning…
          </>
        ) : (
          <>
            <Search size={14} />
            Scan
          </>
        )}
      </button>
    </form>
  );
}
