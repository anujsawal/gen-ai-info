"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Send, Download } from "lucide-react";
import { useState } from "react";

export default function NewslettersPage() {
  const { data: newsletters, isLoading } = useQuery({ queryKey: ["newsletters"], queryFn: api.listNewsletters });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data: detail } = useQuery({
    queryKey: ["newsletter-detail", selectedId],
    queryFn: () => api.getNewsletter(selectedId!),
    enabled: !!selectedId,
  });
  const qc = useQueryClient();
  const sendMutation = useMutation({
    mutationFn: (id: string) => api.sendNewsletter(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["newsletters"] }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Newsletters</h1>
        <p className="text-muted-foreground text-sm">Generated newsletters — preview, download, and send to WhatsApp</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          {isLoading && <p className="text-muted-foreground text-sm">Loading...</p>}
          {newsletters?.map((nl: { id: string; title: string; status: string; faithfulness_score: number; generated_at: string; sent_at: string }) => (
            <Card
              key={nl.id}
              className={`cursor-pointer transition-colors ${selectedId === nl.id ? "ring-1 ring-violet-500" : ""}`}
              onClick={() => setSelectedId(nl.id)}
            >
              <CardContent className="pt-3 pb-3 flex items-center justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{nl.title || "Untitled Newsletter"}</p>
                  <p className="text-[11px] text-muted-foreground">{nl.generated_at?.slice(0, 10)}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {nl.faithfulness_score != null && (
                    <span className="text-[10px] text-muted-foreground">{Math.round(nl.faithfulness_score * 100)}% faithful</span>
                  )}
                  <Badge variant={nl.status === "sent" ? "default" : "secondary"} className="text-[10px]">{nl.status}</Badge>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="w-7 h-7"
                    onClick={e => { e.stopPropagation(); sendMutation.mutate(nl.id); }}
                    disabled={nl.status === "sent" || sendMutation.isPending}
                  >
                    <Send className="w-3 h-3" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
          {!isLoading && !newsletters?.length && <p className="text-muted-foreground text-sm">No newsletters yet — use the Pipeline page to generate one.</p>}
        </div>

        {detail && (
          <Card className="overflow-auto max-h-[600px]">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm">{detail.title}</CardTitle>
              <div className="flex gap-1">
                <a
                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/newsletter/${detail.id}/pdf`}
                  target="_blank"
                  className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground"
                >
                  <Download className="w-3 h-3" /> PDF
                </a>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-3 text-xs">
                <span>Faithfulness: <strong>{Math.round((detail.quality_metrics?.faithfulness_score || 0) * 100)}%</strong></span>
                <span>QA Retries: <strong>{detail.quality_metrics?.qa_retries || 0}</strong></span>
                <Badge variant={detail.qa_report?.approved ? "default" : "destructive"} className="text-[10px]">
                  QA {detail.qa_report?.approved ? "Approved" : "Caveats"}
                </Badge>
              </div>

              {detail.content?.executive_summary?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1">Executive Summary</p>
                  <ul className="text-xs text-muted-foreground space-y-1 list-disc pl-4">
                    {detail.content.executive_summary.map((b: string, i: number) => <li key={i}>{b}</li>)}
                  </ul>
                </div>
              )}

              {detail.content?.sections?.map((section: { section_name: string; content: { headline: string; summary_bullets: string[]; key_insight: string; source_url: string }[] }, i: number) => (
                <div key={i}>
                  <p className="text-xs font-semibold text-violet-400 uppercase tracking-wide mb-1">{section.section_name}</p>
                  {section.content?.map((item, j: number) => (
                    <div key={j} className="bg-muted rounded p-2 mb-1.5 text-xs">
                      <p className="font-medium">{item.headline}</p>
                      {item.summary_bullets?.length > 0 && (
                        <ul className="mt-1 list-disc pl-4 text-muted-foreground space-y-0.5">
                          {item.summary_bullets.map((b: string, k: number) => <li key={k}>{b}</li>)}
                        </ul>
                      )}
                      {item.key_insight && <p className="italic text-muted-foreground mt-1">💡 {item.key_insight}</p>}
                      {item.source_url && <a href={item.source_url} className="text-violet-400 text-[10px] mt-1 block truncate" target="_blank">{item.source_url}</a>}
                    </div>
                  ))}
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
