// Use the SSR client instead of direct supabase-js
// This ensures proper cookie handling for auth
import { createClient } from '@/utils/supabase/client'

// Export a function to get the client instance
// This ensures we always get a properly configured client
export function getSupabaseClient() {
  return createClient()
}

// For backward compatibility, export a client instance
// Note: It's better to use getSupabaseClient() for each request
export const supabase = createClient()