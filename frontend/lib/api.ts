const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

export const api = {
  // Ingestion
  triggerIngestion: () => apiFetch("/api/ingest/trigger", { method: "POST" }),
  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_BASE}/api/ingest/upload`, { method: "POST", body: form }).then(r => r.json());
  },

  // Newsletter
  generateNewsletter: (lookbackDays = 7) =>
    apiFetch(`/api/newsletter/generate?lookback_days=${lookbackDays}`, { method: "POST" }),
  generateAndSend: (lookbackDays = 7) =>
    apiFetch(`/api/newsletter/generate-and-send?lookback_days=${lookbackDays}`, { method: "POST" }),
  sendNewsletter: (id: string) =>
    apiFetch(`/api/newsletter/send/${id}`, { method: "POST" }),
  listNewsletters: () => apiFetch("/api/newsletter/list"),
  getNewsletter: (id: string) => apiFetch(`/api/newsletter/${id}`),

  // Search
  search: (q: string, category?: string) =>
    apiFetch(`/api/search?q=${encodeURIComponent(q)}${category ? `&category=${category}` : ""}`),

  // Sources
  listSources: () => apiFetch("/api/sources"),
  toggleSource: (id: string) => apiFetch(`/api/sources/${id}/toggle`, { method: "PATCH" }),
  deleteSource: (id: string) => apiFetch(`/api/sources/${id}`, { method: "DELETE" }),

  // Governance
  getAuditLog: (actor?: string) =>
    apiFetch(`/api/governance/audit-log${actor ? `?actor=${actor}` : ""}`),
  getGovernanceMetrics: () => apiFetch("/api/governance/metrics/summary"),
  getArticleLineage: (id: string) => apiFetch(`/api/governance/lineage/article/${id}`),
  getNewsletterLineage: (id: string) => apiFetch(`/api/governance/lineage/newsletter/${id}`),
  responsibleAiCheck: () => apiFetch("/api/governance/responsible-ai/check"),

  // Pipeline status
  getPipelineStatus: () => apiFetch("/api/pipeline/status"),
  getHealth: () => apiFetch("/health"),
};
