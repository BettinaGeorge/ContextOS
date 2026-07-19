"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSession } from "@/lib/useSession";
import { ApiError, askQuestion, type AskResponse } from "@/lib/api";

const ORIGIN_LABEL: Record<string, string> = {
  explicit: "Explicit link",
  "metadata-derived": "Metadata-derived",
  inferred: "Inferred (semantic match)",
};

export default function AskPage() {
  const { token, loading } = useSession();
  const [question, setQuestion] = useState("");
  const [notionDocUrl, setNotionDocUrl] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setAsking(true);
    setError(null);
    setResult(null);
    try {
      const response = await askQuestion(token, question, notionDocUrl || undefined);
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to get an answer");
    } finally {
      setAsking(false);
    }
  }

  if (loading) {
    return <PageShell><p className="text-sm text-zinc-500">Loading...</p></PageShell>;
  }

  return (
    <PageShell>
      <div className="flex w-full max-w-xl flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Trace a spec/doc to code</CardTitle>
            <CardDescription>
              Ask what code implements a Notion doc — every answer is cited, or the system says
              it doesn&apos;t know.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAsk} className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="question">Question</Label>
                <Input
                  id="question"
                  required
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="What implements the spinner widget?"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="notion-doc-url">Notion doc URL (optional)</Label>
                <Input
                  id="notion-doc-url"
                  value={notionDocUrl}
                  onChange={(e) => setNotionDocUrl(e.target.value)}
                  placeholder="https://notion.so/..."
                />
              </div>
              <Button type="submit" disabled={asking}>
                {asking ? "Asking..." : "Ask"}
              </Button>
              {error && <p className="text-sm text-red-600">{error}</p>}
            </form>
          </CardContent>
        </Card>

        {result && (
          <Card data-testid="answer-card">
            <CardHeader>
              <CardTitle>{result.abstained ? "No confident answer" : "Answer"}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <p className="text-sm text-zinc-800 dark:text-zinc-200">{result.answer}</p>

              {!result.abstained && result.citations.length > 0 && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-medium text-zinc-500 uppercase">Citations</p>
                  {result.citations.map((c) => (
                    <a
                      key={c.artifact_id}
                      href={c.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between rounded-md border border-zinc-200 px-3 py-2 text-sm hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
                    >
                      <span className="truncate">{c.source_url}</span>
                      <span
                        className={
                          c.origin === "inferred"
                            ? "ml-2 shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                            : "ml-2 shrink-0 rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                        }
                      >
                        {ORIGIN_LABEL[c.origin] ?? c.origin}
                      </span>
                    </a>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </PageShell>
  );
}

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 p-8 dark:bg-black">
      {children}
    </div>
  );
}
