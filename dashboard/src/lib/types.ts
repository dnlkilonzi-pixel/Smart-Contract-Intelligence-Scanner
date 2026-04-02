// Shared TypeScript types matching backend Pydantic schemas

export type RiskLevel = "low" | "medium" | "high" | "critical" | "unknown";

export interface VulnerabilityOut {
  tool: string;
  check: string;
  title: string;
  description?: string;
  severity: string;
  confidence?: string;
  file_path?: string;
  line_start?: number;
  line_end?: number;
  ai_category?: string;
  ai_confidence?: number;
}

export interface ContractProfileOut {
  is_proxy: boolean;
  has_mint: boolean;
  has_ownership: boolean;
  creator_address?: string;
}

export interface ScanResponse {
  contract_id: number;
  address?: string;
  name?: string;
  risk_score: number;
  risk_level: RiskLevel;
  vulnerability_count: number;
  vulnerabilities: VulnerabilityOut[];
  profile: ContractProfileOut;
  scan_status: string;
}

export interface WalletIntelligenceOut {
  address: string;
  tx_count: number;
  eth_balance?: number;
  first_seen_block?: number;
  last_seen_block?: number;
  is_contract_deployer: boolean;
  is_rug_pull_suspect: boolean;
  rugpull_score?: number;
  flash_loan_count: number;
  unique_contracts_interacted: number;
  risk_indicators: string[];
  raw_intelligence?: Record<string, unknown>;
}

export interface GraphNode {
  id: string;
  type: "wallet" | "contract";
  label: string;
  eth_balance?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: "deployed" | "called" | "funded";
  tx_hash?: string;
  value_eth?: number;
}

export interface WalletGraph {
  center: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: { node_count: number; edge_count: number; depth: number };
}

// Real-time threat alert from WebSocket
export interface ThreatAlert {
  type: "threat_alert" | "ping";
  address?: string;
  creator?: string;
  risk_score?: number;
  risk_level?: RiskLevel;
  vulnerability_count?: number;
  reasons?: string[];
}
