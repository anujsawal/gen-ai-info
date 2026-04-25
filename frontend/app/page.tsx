"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { FileText, Database, Shield, Activity, CheckCircle, AlertTriangle } from "lucide-react";

export default function DashboardPage() {
  const { data: metrics } = useQuery({ queryKey: ["governance-metrics"], queryFn: api.getGovernanceMetrics });
  const { data: newsletters } = useQuery({ queryKey: ["newsletters"], queryFn: api.listNewsletters });
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: api.getHealth, refetchInterval: 30000 });

  const faithfulness = metrics?.articles?.avg_faithfulness_score ?? 0;
  const hallucination = metrics?.articles?.avg_hallucination_score ?? 0;
  const totalArticles = metrics?.articles?.total ?? 0;
  const totalNewsletters = metrics?.newsletters?.total ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground text-sm">Gen AI Info Pipeline overview</p>
        </div>
        <Badge variant={health?.status === "ok" ? "default" : "destructive"} className="gap-1">
          {health?.status === "ok" ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
          {health?.status === "ok" ? "API Online" : "API Offline"}
        </Badge>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground flex items-center gap-1"><Database className="w-3 h-3" /> Articles</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold">{totalArticles}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground flex items-center gap-1"><FileText className="w-3 h-3" /> Newsletters</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold">{totalNewsletters}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground flex items-center gap-1"><Shield className="w-3 h-3" /> Faithfulness</CardTitle></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{Math.round(faithfulness * 100)}%</p>
            <Progress value={faithfulness * 100} className="mt-1 h-1" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground flex items-center gap-1"><Activity className="w-3 h-3" /> Hallucination Risk</CardTitle></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{Math.round(hallucination * 100)}%</p>
            <Progress value={hallucination * 100} className="mt-1 h-1" />
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-sm">Agent Activity</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {metrics?.agent_activity && Object.entries(metrics.agent_activity).map(([actor, count]) => (
              <div key={actor} className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground capitalize">{actor.replace(/_/g, " ")}</span>
                <Badge variant="outline">{String(count)} actions</Badge>
              </div>
            ))}
            {!metrics?.agent_activity && <p className="text-muted-foreground text-sm">No data yet — run ingestion first</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-sm">Recent Newsletters</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {newsletters?.slice(0, 5).map((nl: { id: string; title: string; status: string; faithfulness_score: number }) => (
              <div key={nl.id} className="flex items-center justify-between text-sm">
                <span className="truncate max-w-[160px]">{nl.title || "Untitled"}</span>
                <div className="flex items-center gap-2">
                  {nl.faithfulness_score != null && (
                    <Badge variant="outline" className="text-[10px]">{Math.round(nl.faithfulness_score * 100)}% faithful</Badge>
                  )}
                  <Badge variant={nl.status === "sent" ? "default" : "secondary"} className="text-[10px]">{nl.status}</Badge>
                </div>
              </div>
            ))}
            {!newsletters?.length && <p className="text-muted-foreground text-sm">No newsletters yet</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
