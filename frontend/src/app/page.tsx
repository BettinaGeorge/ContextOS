"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSession } from "@/lib/useSession";
import { ApiError, createWorkspace, getMe, type Workspace } from "@/lib/api";

export default function WorkspacePage() {
  const { session, loading, token, signInWithEmail, signOut } = useSession();
  const [email, setEmail] = useState("");
  const [magicLinkSent, setMagicLinkSent] = useState(false);
  const [workspaceId, setWorkspaceId] = useState<string | null | undefined>(undefined);
  const [workspaceName, setWorkspaceName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    getMe(token)
      .then((me) => setWorkspaceId(me.workspace_id))
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load account"));
  }, [token]);

  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const { error: signInError } = await signInWithEmail(email);
    if (signInError) {
      setError(signInError.message);
      return;
    }
    setMagicLinkSent(true);
  }

  async function handleCreateWorkspace(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setCreating(true);
    setError(null);
    try {
      const workspace: Workspace = await createWorkspace(token, workspaceName);
      setWorkspaceId(workspace.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create workspace");
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return <PageShell><p className="text-sm text-zinc-500">Loading...</p></PageShell>;
  }

  if (!session) {
    return (
      <PageShell>
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>Sign in to ContextOS</CardTitle>
            <CardDescription>
              {magicLinkSent
                ? "Check your email for a sign-in link."
                : "Enter your email to receive a magic sign-in link."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!magicLinkSent && (
              <form onSubmit={handleSignIn} className="flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                  />
                </div>
                <Button type="submit">Send magic link</Button>
                {error && <p className="text-sm text-red-600">{error}</p>}
              </form>
            )}
          </CardContent>
        </Card>
      </PageShell>
    );
  }

  return (
    <PageShell>
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Workspace</CardTitle>
          <CardDescription>Signed in as {session.user.email}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {workspaceId === undefined && <p className="text-sm text-zinc-500">Loading workspace...</p>}

          {workspaceId === null && (
            <form onSubmit={handleCreateWorkspace} className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="workspace-name">Workspace name</Label>
                <Input
                  id="workspace-name"
                  required
                  value={workspaceName}
                  onChange={(e) => setWorkspaceName(e.target.value)}
                  placeholder="My Workspace"
                />
              </div>
              <Button type="submit" disabled={creating}>
                {creating ? "Creating..." : "Create workspace"}
              </Button>
              {error && <p className="text-sm text-red-600">{error}</p>}
            </form>
          )}

          {typeof workspaceId === "string" && (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-zinc-600">Workspace ready.</p>
              <div className="flex gap-2">
                <Link href="/connect" className={buttonVariants({ variant: "outline" })}>
                  Connect tools
                </Link>
                <Link href="/ask" className={buttonVariants({ variant: "outline" })}>
                  Ask a question
                </Link>
              </div>
            </div>
          )}

          <Button variant="ghost" onClick={signOut} className="self-start">
            Sign out
          </Button>
        </CardContent>
      </Card>
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
