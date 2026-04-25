"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const AGENTS = [
  { id: "pm_agent", name: "PM Agent", role: "Editorial Prioritization", model: "Llama 3.3 70B", color: "text-violet-400" },
  { id: "designer_agent", name: "Designer Agent", role: "Newsletter Layout", model: "Llama 3.1 8B", color: "text-blue-400" },
  { id: "developer_agent", name: "Developer Agent", role: "Content Writing", model: "Llama 3.3 70B", color: "text-green-400" },
  { id: "qa_agent", name: "QA Agent", role: "Quality & Hallucination Check", model: "Llama 3.3 70B", color: "text-orange-400" },
];

export default function AgentsPage() {
  const { data: audit } = useQuery({ queryKey: ["audit-log"], queryFn: () => api.getAuditLog() });
  const { data: newsletters } = useQuery({ queryKey: ["newsletters"], queryFn: api.listNewsletters });

  const latestNewsletter = newsletters?.[0];
  const { data: nlDetail } = useQuery({
    queryKey: ["newsletter-detail", latestNewsletter?.id],
    queryFn: () => api.getNewsletter(latestNewsletter!.id),
    enabled: !!latestNewsletter?.id,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">AI Team</h1>
        <p className="text-muted-foreground text-sm">4-agent editorial team — PM → Designer → Developer → QA</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {AGENTS.map(agent => (
          <Card key={agent.id}>
            <CardHeader className="pb-2">
              <CardTitle className={`text-sm ${agent.color}`}>{agent.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              <p className="text-xs text-muted-foreground">{agent.role}</p>
              <Badge variant="outline" className="text-[10px]">{agent.model}</Badge>
              <p className="text-xs text-muted-foreground">
                {audit?.filter((a: { actor: string }) => a.actor === agent.id).length || 0} logged actions
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {nlDetail && (
        <Tabs defaultValue="pm">
          <TabsList>
            <TabsTrigger value="pm">PM Agenda</TabsTrigger>
            <TabsTrigger value="designer">Designer Blueprint</TabsTrigger>
            <TabsTrigger value="qa">QA Report</TabsTrigger>
          </TabsList>

          <TabsContent value="pm">
            <Card>
              <CardHeader><CardTitle className="text-sm">Latest PM Agent Decisions</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground">{nlDetail.pm_agenda?.editorial_note}</p>
                <div className="space-y-1">
                  <p className="text-xs font-semibold">Top Stories Selected:</p>
                  {nlDetail.pm_agenda?.top_stories?.map((s: { cluster_id: string; importance_score: number; reason_selected: string }, i: number) => (
                    <div key={i} className="text-xs p-2 bg-muted rounded">
                      <span className="text-violet-400">Cluster {s.cluster_id?.slice(-8)}</span>
                      <span className="text-muted-foreground ml-2">importance: {Math.round((s.importance_score || 0) * 100)}%</span>
                      <p className="text-muted-foreground mt-0.5">{s.reason_selected}</p>
                    </div>
                  ))}
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-red-400">Rejected:</p>
                  {nlDetail.pm_agenda?.rejected?.map((r: { cluster_id: string; reason_rejected: string }, i: number) => (
                    <p key={i} className="text-xs text-muted-foreground">• Cluster {r.cluster_id?.slice(-8)}: {r.reason_rejected}</p>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="designer">
            <Card>
              <CardHeader><CardTitle className="text-sm">Designer Blueprint</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                <p className="text-xs font-semibold">{nlDetail.designer_blueprint?.newsletter_title}</p>
                <p className="text-xs text-muted-foreground">{nlDetail.designer_blueprint?.layout_rationale}</p>
                {nlDetail.designer_blueprint?.sections?.map((s: { section_name: string; format: string; tone: string; design_notes: string }, i: number) => (
                  <div key={i} className="text-xs p-2 bg-muted rounded">
                    <p className="font-medium">{s.section_name}</p>
                    <p className="text-muted-foreground">Format: {s.format} · Tone: {s.tone}</p>
                    <p className="text-muted-foreground mt-0.5">{s.design_notes}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="qa">
            <Card>
              <CardHeader><CardTitle className="text-sm">QA Agent Report</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center gap-3">
                  <Badge variant={nlDetail.qa_report?.approved ? "default" : "destructive"}>
                    {nlDetail.qa_report?.approved ? "Approved" : "Issues Found"}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    Faithfulness: {Math.round((nlDetail.qa_report?.overall_faithfulness_score || 0) * 100)}%
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Coverage: {Math.round((nlDetail.qa_report?.coverage_score || 0) * 100)}%
                  </span>
                </div>
                {nlDetail.qa_report?.bias_flags?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-yellow-400">Bias Flags:</p>
                    {nlDetail.qa_report.bias_flags.map((f: string, i: number) => <p key={i} className="text-xs text-muted-foreground">• {f}</p>)}
                  </div>
                )}
                {nlDetail.qa_report?.improvement_suggestions?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold">Improvement Notes:</p>
                    {nlDetail.qa_report.improvement_suggestions.map((s: string, i: number) => <p key={i} className="text-xs text-muted-foreground">• {s}</p>)}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}

      <Card>
        <CardHeader><CardTitle className="text-sm">Audit Trail</CardTitle></CardHeader>
        <CardContent className="space-y-1.5 max-h-64 overflow-auto">
          {audit?.slice(0, 20).map((log: { id: string; actor: string; action: string; reasoning: string; timestamp: string }) => (
            <div key={log.id} className="flex items-start gap-2 text-xs">
              <Badge variant="outline" className="text-[10px] shrink-0">{log.actor}</Badge>
              <div>
                <span className="font-medium">{log.action}</span>
                {log.reasoning && <p className="text-muted-foreground">{log.reasoning}</p>}
              </div>
              <span className="text-muted-foreground text-[10px] ml-auto shrink-0">{log.timestamp?.slice(11, 19)}</span>
            </div>
          ))}
          {!audit?.length && <p className="text-muted-foreground text-sm">No audit entries yet</p>}
        </CardContent>
      </Card>
    </div>
  );
}
