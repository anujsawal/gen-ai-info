"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Globe, Video, Mail, FlaskConical, Trash2, Plus, Search, Loader2 } from "lucide-react";

const TYPE_ICONS: Record<string, React.ElementType> = {
  website: Globe,
  youtube: Video,
  newsletter: Mail,
  arxiv: FlaskConical,
  upload: Globe,
};

type DetectResult = {
  type: string;
  url: string;
  fetch_config: Record<string, unknown>;
};

type SourceForm = {
  name: string;
  url: string;
  type: string;
  fetch_config: Record<string, unknown>;
};

export default function SourcesPage() {
  const qc = useQueryClient();
  const { data: sources, isLoading } = useQuery({ queryKey: ["sources"], queryFn: api.listSources });

  const [detectUrl, setDetectUrl] = useState("");
  const [detected, setDetected] = useState<DetectResult | null>(null);
  const [form, setForm] = useState<SourceForm>({ name: "", url: "", type: "website", fetch_config: {} });
  const [detecting, setDetecting] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const toggleMutation = useMutation({
    mutationFn: (id: string) => api.toggleSource(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteSource(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });
  const createMutation = useMutation({
    mutationFn: (data: Parameters<typeof api.createSource>[0]) => api.createSource(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sources"] });
      setShowForm(false);
      setDetected(null);
      setDetectUrl("");
      setForm({ name: "", url: "", type: "website", fetch_config: {} });
    },
  });

  async function handleDetect() {
    if (!detectUrl.trim()) return;
    setDetecting(true);
    try {
      const result = await api.detectSource(detectUrl.trim());
      setDetected(result);
      setForm({ name: "", url: result.url, type: result.type, fetch_config: result.fetch_config });
      setShowForm(true);
    } finally {
      setDetecting(false);
    }
  }

  function handleSave() {
    if (!form.name.trim()) return;
    createMutation.mutate({
      name: form.name,
      url: form.url || undefined,
      type: form.type as Parameters<typeof api.createSource>[0]["type"],
      active: true,
      fetch_config: form.fetch_config,
    });
  }

  const grouped = sources?.reduce((acc: Record<string, typeof sources>, s: { type: string }) => {
    acc[s.type] = acc[s.type] || [];
    acc[s.type].push(s);
    return acc;
  }, {}) ?? {};

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Sources</h1>
        <p className="text-muted-foreground text-sm">Manage ingestion sources — enable/disable or add new ones</p>
      </div>

      {/* Add Source */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Plus className="w-4 h-4" /> Add Source
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="Paste a URL (YouTube, blog, RSS, arxiv.org…)"
              value={detectUrl}
              onChange={e => setDetectUrl(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleDetect()}
              className="text-sm"
            />
            <Button onClick={handleDetect} disabled={detecting || !detectUrl.trim()} size="sm" variant="outline">
              {detecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              <span className="ml-1">Detect</span>
            </Button>
          </div>

          {showForm && (
            <div className="space-y-2 border rounded p-3 bg-muted/40">
              {detected && (
                <p className="text-xs text-muted-foreground">
                  Detected as <strong>{detected.type}</strong>
                  {detected.fetch_config?.channel_id ? ` · channel_id: ${detected.fetch_config.channel_id}` : ""}
                </p>
              )}
              <Input
                placeholder="Source name (e.g. VentureBeat AI)"
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                className="text-sm"
              />
              {form.type === "youtube" && !form.fetch_config?.channel_id && (
                <Input
                  placeholder="YouTube channel_id (e.g. UCbfYPyITQ-7l4upoX8nvctg)"
                  value={(form.fetch_config?.channel_id as string) || ""}
                  onChange={e => setForm(f => ({ ...f, fetch_config: { ...f.fetch_config, channel_id: e.target.value } }))}
                  className="text-sm font-mono"
                />
              )}
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={handleSave}
                  disabled={!form.name.trim() || createMutation.isPending}
                >
                  {createMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
                  Save Source
                </Button>
                <Button size="sm" variant="ghost" onClick={() => { setShowForm(false); setDetected(null); }}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

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
        <p className="text-muted-foreground text-sm">No sources yet. Run ingestion to auto-load from config, or add one above.</p>
      )}
    </div>
  );
}
