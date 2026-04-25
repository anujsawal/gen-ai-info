"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { Globe, Video, Mail, FlaskConical, Trash2 } from "lucide-react";

const TYPE_ICONS: Record<string, React.ElementType> = {
  website: Globe,
  youtube: Video,
  newsletter: Mail,
  arxiv: FlaskConical,
  upload: Globe,
};

export default function SourcesPage() {
  const qc = useQueryClient();
  const { data: sources, isLoading } = useQuery({ queryKey: ["sources"], queryFn: api.listSources });

  const toggleMutation = useMutation({
    mutationFn: (id: string) => api.toggleSource(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteSource(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });

  const grouped = sources?.reduce((acc: Record<string, typeof sources>, s: { type: string }) => {
    acc[s.type] = acc[s.type] || [];
    acc[s.type].push(s);
    return acc;
  }, {}) ?? {};

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Sources</h1>
        <p className="text-muted-foreground text-sm">Manage ingestion sources — enable/disable individual sources</p>
      </div>

      {isLoading && <p className="text-muted-foreground text-sm">Loading sources...</p>}

      {Object.entries(grouped).map(([type, items]) => {
        const Icon = TYPE_ICONS[type as keyof typeof TYPE_ICONS] || Globe;
        return (
          <Card key={type}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Icon className="w-4 h-4" />
                {type.charAt(0).toUpperCase() + type.slice(1)} Sources
                <Badge variant="outline">{(items as unknown[]).length}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {(items as { id: string; name: string; url: string; active: boolean; last_fetched_at: string }[]).map(source => (
                <div key={source.id} className="flex items-center justify-between p-2 bg-muted rounded text-sm">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{source.name}</p>
                    {source.url && <p className="text-[10px] text-muted-foreground truncate">{source.url}</p>}
                    {source.last_fetched_at && <p className="text-[10px] text-muted-foreground">Last: {source.last_fetched_at.slice(0, 10)}</p>}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge
                      variant={source.active ? "default" : "secondary"}
                      className="text-[10px] cursor-pointer"
                      onClick={() => toggleMutation.mutate(source.id)}
                    >
                      {source.active ? "Active" : "Inactive"}
                    </Badge>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="w-6 h-6 text-destructive hover:text-destructive"
                      onClick={() => deleteMutation.mutate(source.id)}
                    >
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        );
      })}

      {!isLoading && !sources?.length && (
        <p className="text-muted-foreground text-sm">No sources configured. Run ingestion to auto-load sources from config/sources.yaml.</p>
      )}
    </div>
  );
}
