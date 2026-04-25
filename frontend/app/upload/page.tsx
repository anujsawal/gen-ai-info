"use client";
import { useState, useRef } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Upload, FileText, CheckCircle } from "lucide-react";

export default function UploadPage() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{ article_id: string; title: string; chunks: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setUploading(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.uploadDocument(file);
      if (data.article_id) {
        setResult(data);
      } else {
        setError(data.detail || "Upload failed");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Upload Document</h1>
        <p className="text-muted-foreground text-sm">Upload a PDF, research paper, or text file for RAG analysis. The document will be embedded and searchable.</p>
      </div>

      <Card
        className={`border-2 border-dashed transition-colors cursor-pointer ${dragging ? "border-violet-400 bg-violet-500/5" : "border-border hover:border-violet-500/50"}`}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
        onClick={() => inputRef.current?.click()}
      >
        <CardContent className="py-12 flex flex-col items-center gap-3 text-center">
          <Upload className="w-10 h-10 text-muted-foreground" />
          <div>
            <p className="font-medium">Drop a file here or click to browse</p>
            <p className="text-sm text-muted-foreground mt-1">Supported: PDF, TXT, MD</p>
          </div>
          <input ref={inputRef} type="file" accept=".pdf,.txt,.md" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
        </CardContent>
      </Card>

      {uploading && (
        <Card>
          <CardContent className="py-4 flex items-center gap-3 text-sm">
            <div className="w-4 h-4 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
            Processing document — embedding and chunking...
          </CardContent>
        </Card>
      )}

      {result && (
        <Card className="border-green-500/30">
          <CardContent className="py-4 flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-green-400" />
            <div>
              <p className="text-sm font-medium">{result.title}</p>
              <p className="text-xs text-muted-foreground">{result.chunks} chunks embedded and stored · Article ID: {result.article_id.slice(0, 8)}...</p>
            </div>
            <Badge variant="default" className="ml-auto">Indexed</Badge>
          </CardContent>
        </Card>
      )}

      {error && (
        <Card className="border-destructive/30">
          <CardContent className="py-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-sm">How it works</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-xs text-muted-foreground">
          <p>1. Upload a PDF or text file (research paper, report, article)</p>
          <p>2. Content is cleaned, chunked (512 tokens), and embedded using nomic-embed-text-v1</p>
          <p>3. Embeddings stored in PostgreSQL + pgvector for semantic search</p>
          <p>4. Article is available in RAG Search immediately</p>
          <p>5. Next newsletter generation will include uploaded content if relevant</p>
        </CardContent>
      </Card>
    </div>
  );
}
