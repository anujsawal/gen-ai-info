"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Play, ArrowRight, RotateCcw } from "lucide-react";
import { useState } from "react";

const PIPELINE_STAGES = [
  { id: "scraper", label: "Scraper", description: "Web, YouTube, RSS, ArXiv" },
  { id: "cleaner", label: "Cleaner", description: "Normalize, deduplicate" },
  { id: "embedder", label: "Embedder", description: "nomic-embed-text-v1" },
  { id: "clusterer", label: "Clusterer", description: "HDBSCAN semantic groups" },
  { id: "storage", label: "Storage", description: "PostgreSQL + pgvector" },
];

const NEWSLETTER_STAGES = [
  { id: "retrieval", label: "Retrieval", description: "RAG from pgvector" },
  { id: "pm", label: "PM Agent", description: "Editorial prioritization" },
  { id: "designer", label: "Designer", description: "Layout blueprint" },
  { id: "developer", label: "Developer", description: "Write content" },
  { id: "qa", label: "QA Agent", description: "Hallucination check" },
  { id: "pdf", label: "PDF + Send", description: "WeasyPrint + WhatsApp" },
];

type StageStatus = "idle" | "running" | "done" | "error";

export default function PipelinePage() {
  const [ingestionStatus, setIngestionStatus] = useState<Record<string, StageStatus>>({});
  const [newsletterStatus, setNewsletterStatus] = useState<Record<string, StageStatus>>({});
  const [log, setLog] = useState<string[]>([]);

  const qc = useQueryClient();

  const addLog = (msg: string) => setLog(prev => [`${new Date().toLocaleTimeString()} — ${msg}`, ...prev.slice(0, 49)]);

  const ingestMutation = useMutation({
    mutationFn: api.triggerIngestion,
    onMutate: () => {
      const s: Record<string, StageStatus> = {};
      PIPELINE_STAGES.forEach(stage => { s[stage.id] = "idle"; });
      s["scraper"] = "running";
      setIngestionStatus(s);
      addLog("Ingestion pipeline started");
    },
    onSuccess: () => {
      const s: Record<string, StageStatus> = {};
      PIPELINE_STAGES.forEach(stage => { s[stage.id] = "done"; });
      setIngestionStatus(s);
      addLog("Ingestion pipeline completed");
      qc.invalidateQueries({ queryKey: ["governance-metrics"] });
    },
    onError: (e) => {
      addLog(`Ingestion failed: ${e.message}`);
    },
  });

  const newsletterMutation = useMutation({
    mutationFn: () => api.generateAndSend(7),
    onMutate: () => {
      const s: Record<string, StageStatus> = {};
      NEWSLETTER_STAGES.forEach(stage => { s[stage.id] = "idle"; });
      s["retrieval"] = "running";
      setNewsletterStatus(s);
      addLog("Newsletter generation started");
    },
    onSuccess: (data) => {
      const s: Record<string, StageStatus> = {};
      NEWSLETTER_STAGES.forEach(stage => { s[stage.id] = "done"; });
      setNewsletterStatus(s);
      addLog(`Newsletter generated! Faithfulness: ${Math.round((data.faithfulness_score || 0) * 100)}%`);
      if (data.whatsapp?.success) addLog("WhatsApp notification sent");
      qc.invalidateQueries({ queryKey: ["newsletters"] });
    },
    onError: (e) => addLog(`Newsletter failed: ${e.message}`),
  });

  const stageColor = (s: StageStatus) => {
    if (s === "done") return "bg-green-500/20 border-green-500 text-green-400";
    if (s === "running") return "bg-violet-500/20 border-violet-400 text-violet-300 animate-pulse";
    if (s === "error") return "bg-red-500/20 border-red-500 text-red-400";
    return "bg-muted border-border text-muted-foreground";
  };

  const renderPipeline = (stages: typeof PIPELINE_STAGES, statuses: Record<string, StageStatus>) => (
    <div className="flex items-center gap-2 flex-wrap">
      {stages.map((stage, i) => (
        <div key={stage.id} className="flex items-center gap-2">
          <div className={`border rounded-lg px-3 py-2 text-center min-w-[90px] ${stageColor(statuses[stage.id] || "idle")}`}>
            <p className="text-xs font-semibold">{stage.label}</p>
            <p className="text-[10px] opacity-70">{stage.description}</p>
          </div>
          {i < stages.length - 1 && <ArrowRight className="w-3 h-3 text-muted-foreground shrink-0" />}
        </div>
      ))}
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Pipeline</h1>
        <p className="text-muted-foreground text-sm">Run and monitor the ingestion and newsletter pipelines</p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm">Ingestion Pipeline</CardTitle>
          <Button size="sm" onClick={() => ingestMutation.mutate()} disabled={ingestMutation.isPending} className="gap-1">
            <Play className="w-3 h-3" /> Run Ingestion
          </Button>
        </CardHeader>
        <CardContent>{renderPipeline(PIPELINE_STAGES, ingestionStatus)}</CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm">Newsletter Pipeline (4-Agent Team)</CardTitle>
          <Button size="sm" onClick={() => newsletterMutation.mutate()} disabled={newsletterMutation.isPending} className="gap-1">
            <RotateCcw className="w-3 h-3" /> Generate & Send
          </Button>
        </CardHeader>
        <CardContent>{renderPipeline(NEWSLETTER_STAGES, newsletterStatus)}</CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-sm">Activity Log</CardTitle></CardHeader>
        <CardContent>
          <div className="font-mono text-xs space-y-1 max-h-48 overflow-auto">
            {log.length === 0 && <p className="text-muted-foreground">No activity yet</p>}
            {log.map((entry, i) => <p key={i} className="text-green-400">{entry}</p>)}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
