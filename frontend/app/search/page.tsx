"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{
    article_id: string; title: string; excerpt: string;
    source_url: string; category: string; similarity_score: number;
    faithfulness_score: number;
  }[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await api.search(query);
      setResults(data.results || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">RAG Search</h1>
        <p className="text-muted-foreground text-sm">Semantic search across all ingested articles and uploaded documents</p>
      </div>

      <div className="flex gap-2">
        <Input
          placeholder="Search AI news... e.g. 'new LLM training technique'"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSearch()}
          className="flex-1"
        />
        <Button onClick={handleSearch} disabled={loading} className="gap-1">
          <Search className="w-4 h-4" /> Search
        </Button>
      </div>

      {loading && <p className="text-muted-foreground text-sm">Searching embeddings...</p>}

      <div className="space-y-3">
        {results.map((r, i) => (
          <Card key={i}>
            <CardContent className="pt-3 pb-3 space-y-1.5">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium flex-1">{r.title}</p>
                <div className="flex items-center gap-1.5 shrink-0">
                  <Badge variant="outline" className="text-[10px]">{r.category}</Badge>
                  <Badge variant="secondary" className="text-[10px]">{Math.round(r.similarity_score * 100)}% match</Badge>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">{r.excerpt}</p>
              {r.source_url && (
                <a href={r.source_url} target="_blank" className="text-violet-400 text-[10px] truncate block">{r.source_url}</a>
              )}
              {r.faithfulness_score != null && (
                <p className="text-[10px] text-muted-foreground">Faithfulness score: {Math.round(r.faithfulness_score * 100)}%</p>
              )}
            </CardContent>
          </Card>
        ))}
        {results.length === 0 && !loading && query && (
          <p className="text-muted-foreground text-sm">No results found. Try a different query or run ingestion first.</p>
        )}
      </div>
    </div>
  );
}
