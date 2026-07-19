"use client";

import { useEffect, useRef, useState } from "react";
import type { SupabaseClient, Session } from "@supabase/supabase-js";
import { createSupabaseClient } from "@/lib/supabase";

export function useSession() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  // Created lazily inside useEffect, not during render, so this never runs
  // during Next.js's build-time static prerendering — only in the browser,
  // after mount. Calling createSupabaseClient() directly in the render body
  // crashes the production build when Supabase env vars aren't set yet
  // (real bug hit while building this: `next build` prerenders "use client"
  // pages on the server too, and @supabase/ssr throws on empty credentials).
  const supabaseRef = useRef<SupabaseClient | null>(null);

  useEffect(() => {
    const supabase = createSupabaseClient();
    supabaseRef.current = supabase;

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  async function signInWithEmail(email: string) {
    if (!supabaseRef.current) {
      return { error: { message: "Not ready yet — try again in a moment." } };
    }
    return supabaseRef.current.auth.signInWithOtp({ email });
  }

  async function signOut() {
    await supabaseRef.current?.auth.signOut();
  }

  return {
    session,
    loading,
    token: session?.access_token ?? null,
    signInWithEmail,
    signOut,
  };
}
