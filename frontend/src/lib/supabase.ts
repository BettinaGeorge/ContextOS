import { createBrowserClient } from "@supabase/ssr";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

// True until a real Supabase project's values replace the placeholders in
// .env.local. Checked before attempting sign-in so the app can refuse up
// front instead of guaranteeing a failed network call — a fetch() to a
// nonexistent host logs to the browser console at the network level
// regardless of whether the JS promise rejection is caught, which is noisy
// in Next's dev overlay for something that isn't actually a bug.
export const isSupabaseConfigured =
  SUPABASE_URL.length > 0 &&
  SUPABASE_ANON_KEY.length > 0 &&
  !SUPABASE_URL.includes("placeholder");

// Reads NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY from
// frontend/.env.local (see .env.example at repo root for the full list).
// Placeholder values won't authenticate against anything real — this client
// only becomes functional once a real Supabase project's values are set.
export function createSupabaseClient() {
  return createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
}
