# OAuth State Error Troubleshooting Guide

## Problem: "bad_oauth_state" Error

This error occurs when the OAuth state parameter stored in cookies doesn't match what comes back from the OAuth provider.

## Solution Steps:

### 1. Check Supabase Dashboard Settings

Go to your Supabase project dashboard:
- Navigate to Authentication > URL Configuration
- Ensure these URLs are added to "Redirect URLs":
  ```
  http://localhost:3000/auth/callback
  http://localhost:3001/auth/callback
  http://192.168.1.103:3001/auth/callback
  ```
- Set "Site URL" to your primary development URL (e.g., `http://192.168.1.103:3001`)

### 2. Clear Browser State

1. Clear all cookies for your development domain
2. Clear localStorage
3. Close all tabs with your app
4. Try signing in again

### 3. Check Network Configuration

If using IP address (192.168.1.103):
- Ensure your computer's IP hasn't changed
- Check that port 3001 is accessible
- Try using localhost:3000 instead

### 4. Environment Variables

Verify your `.env.local` file:
```env
NEXT_PUBLIC_API_URL=http://192.168.1.103:8000
NEXT_PUBLIC_SUPABASE_URL=https://[your-project].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=[your-anon-key]
```

### 5. Development Server Configuration

Restart your Next.js server with explicit host and port:
```bash
npm run dev -- -H 0.0.0.0 -p 3001
```

### 6. Browser Console Debugging

Check the browser console for:
- Cookie warnings
- CORS errors
- Network request failures

Look for these specific logs:
- "OAuth redirect URL: ..."
- "Auth callback params: ..."

### 7. Test with Different Browsers

Try signing in with:
- Chrome (incognito mode)
- Firefox
- Safari

### 8. Temporary Workaround

If the issue persists, try this temporary fix:

1. Update `frontend/providers/AuthProvider.tsx`:
   - Comment out the `signOut({ scope: 'local' })` line in `signInWithGoogle`
   - This prevents clearing existing auth state

2. Use localhost instead of IP:
   ```bash
   # Update .env.local
   NEXT_PUBLIC_API_URL=http://localhost:8000
   
   # Run on localhost
   npm run dev
   ```

### 9. Check Supabase Auth Logs

In Supabase dashboard:
- Go to Logs > Auth
- Look for authentication errors
- Check for rate limiting

### 10. Update Dependencies

Ensure you have the latest versions:
```bash
npm update @supabase/ssr @supabase/supabase-js
```

## Common Causes:

1. **Cookie Domain Mismatch**: Browser treats 192.168.1.103 and localhost as different domains
2. **Secure Cookie on HTTP**: Trying to set secure cookies on non-HTTPS connection
3. **PKCE Verification Failure**: OAuth state/code verifier mismatch
4. **Multiple Auth Sessions**: Conflicting sessions from different login attempts

## If All Else Fails:

1. Create a fresh Supabase project for testing
2. Use ngrok to create an HTTPS tunnel for development
3. Deploy to a staging environment with proper HTTPS

## Related Files Modified:

- `/utils/supabase/client.ts` - Custom cookie handling
- `/utils/supabase/server.ts` - Server-side cookie configuration
- `/utils/supabase/middleware.ts` - Middleware cookie handling
- `/utils/supabase/config.ts` - Configuration helpers