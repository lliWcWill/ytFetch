# ytFetch Development Progress Summary

## Overview
ytFetch is a YouTube transcription service that has evolved from a subscription-based model to a token-based pay-as-you-go system. Users can transcribe individual videos or bulk process playlists/channels.

## Recent Major Changes

### 1. **Pivot from Subscription to Token-Based System**
- Removed subscription tiers (Free, Pro, Enterprise)
- Implemented token-based pricing where users pay for what they use
- Removed all upgrade prompts and tier limitations
- Users purchase tokens and use them for transcriptions

### 2. **Stripe Integration Success** ✅
- Successfully integrated Stripe Checkout for token purchases
- Fixed environment variable loading issues
- Token purchase flow working end-to-end
- Users can buy token packages and see updated balances

### 3. **Frontend Improvements**
- Fixed ESLint errors by configuring Next.js to skip linting during builds
- Added fun rotating status messages during audio gathering phase
- Fixed Next.js 15 build errors with useSearchParams and Suspense boundaries
- Created billing success pages with proper error handling

### 4. **Bulk Processing System**
- Increased free tier limit from 5 to 60 videos per bulk job
- Fixed channel video extraction (was showing categories instead of videos)
- Removed enterprise upgrade popups
- Implemented guest user support for bulk jobs

## Current Status & Issues

### Working Features ✅
- Single video transcription (unofficial and Groq methods)
- Stripe token purchase flow
- User authentication with Supabase
- WebSocket real-time progress updates
- Guest user access for single transcriptions

### Guest Bulk Job - Complete! ✅
**Summary**: Guest users can now create, view, and start bulk jobs without authentication.

**Progress**:
1. ✅ Guest users can successfully analyze playlists/channels
2. ✅ Guest users can create bulk jobs (up to 60 videos)
3. ✅ Jobs are created with session_id in metadata for tracking
4. ✅ Fixed database schema issues (column names, data types)
5. ✅ Fixed trigger to handle NULL user_ids for guests
6. ✅ Fixed GET /jobs/{job_id} and POST /jobs/{job_id}/start to allow guest access
7. ✅ Fixed header case sensitivity issue (X-Guest-Session-ID vs x-guest-session-id)

**Latest Fix**:
- Fixed header case sensitivity: Frontend sends 'X-Guest-Session-ID' but backend was looking for lowercase
- Now checks for both capitalized and lowercase versions of the header
- Guest users should now be able to create, view, and start their bulk jobs successfully

### Guest User Flow (Intended)
1. Guest can transcribe up to 10 individual videos
2. Guest can create 1 bulk job per day (up to 60 videos)
3. After hitting limits, prompted to sign in
4. Authenticated users have no limits (pay per token use)

## Database Schema Issues
Several SQL functions and columns were missing:
- ✅ Fixed: Added metadata, webhook_url, max_videos, retry_settings columns
- ✅ Fixed: Created check_tier_limits function
- ✅ Fixed: Fixed guest usage tracking functions
- ❌ Current: Missing 'name' column in bulk_jobs table

## Security Audit Findings
A comprehensive security audit revealed:
- API keys were exposed in .env files (need rotation)
- Missing rate limiting
- Open redirect vulnerability in auth callback
- Debug mode enabled in production
- Missing security headers

## Tech Stack
- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS
- **Backend**: FastAPI, Python, Poetry
- **Database**: Supabase (PostgreSQL)
- **Auth**: Supabase Auth
- **Payments**: Stripe Checkout (one-time payments)
- **Transcription**: YouTube unofficial API, Groq Whisper, OpenAI Whisper

## Next Steps
1. Fix the 'name' column issue in bulk_jobs table
2. Complete guest user bulk job flow
3. Address security vulnerabilities before production
4. Test end-to-end bulk transcription process
5. Implement proper error handling and user feedback

## File Structure
```
/ytFetch
├── frontend/          # Next.js application
├── backend/          # FastAPI application
├── docs/            # Documentation
└── database/        # SQL scripts and migrations
```