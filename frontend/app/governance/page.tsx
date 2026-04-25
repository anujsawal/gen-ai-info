"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Shield, AlertTriangle, CheckCircle, Activity } from "lucide-react";

export default function GovernancePage() {
  const { data: metrics } = useQuery({ queryKey: ["governance-metrics"], queryFn: api.getGovernanceMetrics });
  const { data: audit } = useQuery({ queryKey: ["audit-log"], queryFn: () => api.getAuditLog() });
  const { data: responsibleAi } = useQuery({ queryKey: ["responsible-ai"], queryFn: api.responsibleAiCheck });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Governance & Responsible AI</h1>
        <p className="text-muted-foreground text-sm">Data lineage, audit trail, AI explainability, bias detection, and quality metrics</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className={`border ${responsibleAi?.passed === false ? "border-destructive/50" : "border-green-500/30"}`}>
          <CardHeader className="pb-2"><CardTitle className="text-xs flex items-center gap-1"><Shield className="w-3 h-3" /> Content Moderation</CardTitle></CardHeader>
          <CardContent className="flex items-center gap-2">
            {responsibleAi?.content_moderation?.safe
              ? <><CheckCircle className="w-4 h-4 text-green-400" /><span className="text-sm text-green-400">Safe</span></>
              : <><AlertTriangle className="w-4 h-4 text-red-400" /><span className="text-sm text-red-400">Issues Found</span></>
            }
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs flex items-center gap-1"><Activity className="w-3 h-3" /> Avg Faithfulness</CardTitle></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{Math.round((metrics?.articles?.avg_faithfulness_score || 0) * 100)}%</p>
            <Progress value={(metrics?.articles?.avg_faithfulness_score || 0) * 100} className="mt-1 h-1" />
          </CardContent>
        </Card>

        <Card className={responsibleAi?.source_bias?.biased ? "border-yellow-500/30" : ""}>
          <CardHeader className="pb-2"><CardTitle className="text-xs flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Source Bias</CardTitle></CardHeader>
          <CardContent>
            {responsibleAi?.source_bias?.biased
              ? <><span className="text-sm text-yellow-400">Bias detected</span><p className="text-[10px] text-muted-foreground mt-1">{responsibleAi.source_bias.recommendation}</p></>
              : <span className="text-sm text-green-400">Balanced</span>
            }
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="audit">
        <TabsList>
          <TabsTrigger value="audit">Audit Trail</TabsTrigger>
          <TabsTrigger value="bias">Source Distribution</TabsTrigger>
          <TabsTrigger value="principles">AI Principles</TabsTrigger>
        </TabsList>

        <TabsContent value="audit">
          <Card>
            <CardContent className="pt-4 space-y-1.5 max-h-72 overflow-auto">
              {audit?.map((log: { id: string; actor: string; action: string; reasoning: string; entity_type: string; timestamp: string }) => (
                <div key={log.id} className="flex items-start gap-2 text-xs p-1.5 hover:bg-muted rounded">
                  <Badge variant="outline" className="text-[10px] shrink-0 capitalize">{log.actor?.replace(/_/g, " ")}</Badge>
                  <div className="flex-1 min-w-0">
                    <span className="font-medium">{log.action}</span>
                    <span className="text-muted-foreground ml-2">({log.entity_type})</span>
                    {log.reasoning && <p className="text-muted-foreground truncate">{log.reasoning}</p>}
                  </div>
                  <span className="text-muted-foreground text-[10px] shrink-0">{log.timestamp?.slice(11, 19)}</span>
                </div>
              ))}
              {!audit?.length && <p className="text-muted-foreground text-sm py-4 text-center">No audit entries yet</p>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="bias">
          <Card>
            <CardContent className="pt-4 space-y-2">
              {responsibleAi?.source_bias?.source_distribution
                ? Object.entries(responsibleAi.source_bias.source_distribution).map(([src, share]) => (
                  <div key={src} className="space-y-0.5">
                    <div className="flex justify-between text-xs">
                      <span>{src}</span>
                      <span className={(share as number) > 0.6 ? "text-yellow-400" : "text-muted-foreground"}>{Math.round((share as number) * 100)}%</span>
                    </div>
                    <Progress value={(share as number) * 100} className="h-1" />
                  </div>
                ))
                : <p className="text-muted-foreground text-sm py-4 text-center">Run ingestion to see source distribution</p>
              }
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="principles">
          <Card>
            <CardContent className="pt-4 space-y-3 text-xs text-muted-foreground">
              <div>
                <p className="font-semibold text-foreground">1. Transparency</p>
                <p>Every agent decision is logged with structured reasoning in the audit trail. Users can trace any newsletter item back to its source.</p>
              </div>
              <div>
                <p className="font-semibold text-foreground">2. Accuracy & Anti-Hallucination</p>
                <p>QA Agent runs faithfulness scoring on all summaries. Items below 70% faithfulness threshold are regenerated (max 2 retries). Scores shown in PDF.</p>
              </div>
              <div>
                <p className="font-semibold text-foreground">3. Source Attribution</p>
                <p>Every article retains its original source URL. Attribution is always included in newsletters and search results. No orphaned content.</p>
              </div>
              <div>
                <p className="font-semibold text-foreground">4. Diversity & Bias Prevention</p>
                <p>Source bias detector flags if any single source accounts for &gt;60% of content. Category distribution ensures balanced coverage across AI topics.</p>
              </div>
              <div>
                <p className="font-semibold text-foreground">5. PII Protection</p>
                <p>All scraped content is screened for personal data (emails, phone numbers) before storage. Flagged content is not ingested.</p>
              </div>
              <div>
                <p className="font-semibold text-foreground">6. Content Safety</p>
                <p>Harmful content patterns are checked during the cleaning phase. Flagged content is excluded with an audit log entry.</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
