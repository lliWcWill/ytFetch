/**
 * Bulk API Service Layer for YouTube Bulk Transcription
 * Provides type-safe interfaces and functions for interacting with the bulk transcription API
 */

import { getApiUrl, ApiNetworkError, ApiHttpError, ApiValidationError, TierLimitError } from './api'

// TypeScript Interfaces for Bulk Operations

export type TranscriptMethod = 'unofficial' | 'groq' | 'openai'
export type OutputFormat = 'txt' | 'srt' | 'vtt' | 'json'
export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'retrying'

export interface BulkAnalyzeRequest {
  url: string
  max_videos?: number
}

export interface BulkCreateRequest {
  url: string
  transcript_method: TranscriptMethod
  output_format: OutputFormat
  max_videos?: number
  webhook_url?: string
}

export interface VideoInfo {
  video_id: string
  title: string
  duration: number
  url: string
  thumbnail_url?: string
  uploader?: string
}

export interface BulkAnalyzeResponse {
  url: string
  source_type: 'playlist' | 'channel'
  title: string
  description?: string
  total_videos: number
  analyzed_videos: number
  estimated_duration_hours: number
  videos: VideoInfo[]
  tier_limits: {
    max_videos_per_job: number
    max_concurrent_jobs: number
    daily_video_limit: number
  }
  can_process_all: boolean
}

export interface BulkTaskResponse {
  task_id: string
  video_id: string
  video_title: string
  video_url: string
  video_duration: number
  status: TaskStatus
  order_index: number
  retry_count: number
  transcript_text?: string
  language?: string
  processing_method?: string
  error_message?: string
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface BulkJobResponse {
  job_id: string
  user_id: string
  source_url: string
  transcript_method: TranscriptMethod
  output_format: OutputFormat
  status: JobStatus
  total_videos: number
  completed_videos: number
  failed_videos: number
  pending_videos?: number
  processing_videos?: number
  retry_videos?: number
  progress_percent: number
  user_tier: string
  webhook_url?: string
  zip_file_path?: string
  zip_available: boolean
  estimated_duration_minutes?: number
  created_at: string
  updated_at: string
  completed_at?: string
  tier_limits?: {
    max_videos_per_job: number
    max_concurrent_jobs: number
    daily_video_limit: number
  }
}

export interface BulkJobListResponse {
  jobs: BulkJobResponse[]
  total_count: number
  page: number
  per_page: number
  has_next: boolean
}

export interface BulkError {
  error: string
  message: string
  details?: Record<string, any>
  status_code: number
}

// Utility Functions

/**
 * Creates headers for API requests with authentication
 */
async function createHeaders(includeContentType = true): Promise<Record<string, string>> {
  const { createAuthHeaders } = await import('@/lib/auth-token');
  const headers = await createAuthHeaders(includeContentType);
  
  // Ensure we have guest session ID for unauthenticated users
  if (!headers['Authorization']) {
    const { getGuestSessionId } = await import('@/lib/auth-token');
    headers['X-Guest-Session-ID'] = getGuestSessionId();
  }
  
  return headers;
}

/**
 * Handles fetch responses with proper error handling and type safety
 */
async function handleResponse<T>(response: Response): Promise<T> {
  // Handle 401 Unauthorized - but check if it's a guest limit error first
  if (response.status === 401) {
    // Try to parse the response to check if it's a guest limit error
    let errorData: any;
    try {
      errorData = await response.json();
    } catch {
      errorData = null;
    }
    
    // Debug logging for 401 errors
    console.log('[BulkAPI] Received 401 error:', errorData);
    
    // Check if it's a guest-related error (don't redirect for these)
    if (errorData?.error === 'guest_limit_exceeded' || 
        errorData?.error_code === 'guest_limit_exceeded' ||
        errorData?.requires_auth === true) {
      throw new ApiHttpError(
        errorData.message || 'Guest limit exceeded. Please sign in to continue.',
        401,
        'Unauthorized',
        errorData
      );
    }
    
    // Check if we have an auth token - if not, this is a guest user
    const { getAuthToken } = await import('@/lib/auth-token');
    const token = await getAuthToken();
    
    if (!token) {
      // Guest user - don't redirect, just throw the error
      console.log('[BulkAPI] Guest user received 401, not redirecting');
      throw new ApiHttpError(
        errorData?.message || 'Guest access limit reached. Please sign in to continue.',
        401,
        'Unauthorized',
        errorData
      );
    }
    
    // Otherwise, it's a real auth error for an authenticated user - redirect to login
    const { handleAuthError } = await import('@/lib/auth-token');
    handleAuthError();
    throw new ApiHttpError('Authentication required', 401, 'Unauthorized', errorData);
  }

  // Check if response is ok
  if (!response.ok) {
    let errorData: any
    try {
      errorData = await response.json()
    } catch {
      errorData = { error: 'Unknown error', message: response.statusText }
    }
    
    throw new ApiHttpError(
      errorData.message || `HTTP ${response.status}: ${response.statusText}`,
      response.status,
      response.statusText,
      errorData
    )
  }

  // Parse JSON response
  try {
    const data = await response.json()
    return data as T
  } catch (error) {
    throw new Error(`Failed to parse JSON response: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

/**
 * Makes a typed bulk API request with error handling
 */
async function bulkApiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${getApiUrl()}${endpoint}`
  
  try {
    const defaultHeaders = await createHeaders();
    
    // Debug logging for guest sessions
    if (!defaultHeaders['Authorization'] && defaultHeaders['X-Guest-Session-ID']) {
      console.log('[BulkAPI] Making request as guest with session ID:', defaultHeaders['X-Guest-Session-ID']);
    }
    
    const response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    })
    
    return await handleResponse<T>(response)
  } catch (error) {
    if (error instanceof ApiHttpError) {
      throw error
    }
    
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ApiNetworkError(
        `Network error: Unable to connect to ${url}`,
        error
      )
    }
    
    throw new ApiNetworkError(
      `Request failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      error instanceof Error ? error : undefined
    )
  }
}

// Main Bulk API Functions

/**
 * Analyzes a YouTube playlist or channel to get video count and metadata
 * @param url - YouTube playlist or channel URL
 * @param maxVideos - Optional maximum number of videos to analyze
 * @returns Promise<BulkAnalyzeResponse>
 */
export async function analyzeBulkSource(
  url: string,
  maxVideos?: number
): Promise<BulkAnalyzeResponse> {
  // Validate required parameters
  if (!url || typeof url !== 'string') {
    throw new ApiValidationError('URL is required and must be a string')
  }
  
  // Basic URL validation for playlists and channels
  const playlistRegex = /(?:youtube\.com\/(?:playlist\?list=|watch\?v=.*&list=))([\w-]+)/
  const channelRegex = /(?:youtube\.com\/(?:@[\w-]+|c\/[\w-]+|channel\/[\w-]+|user\/[\w-]+))/
  
  if (!playlistRegex.test(url) && !channelRegex.test(url)) {
    throw new ApiValidationError('URL must be a valid YouTube playlist or channel URL')
  }

  const requestData: BulkAnalyzeRequest = {
    url,
    ...(maxVideos && { max_videos: maxVideos }),
  }

  try {
    const response = await bulkApiRequest<BulkAnalyzeResponse>('/api/v1/bulk/analyze', {
      method: 'POST',
      body: JSON.stringify(requestData),
    })

    return response
  } catch (error) {
    if (error instanceof ApiHttpError && error.status === 422) {
      throw new ApiValidationError(
        'Validation error: Invalid request parameters',
        error.response?.details
      )
    }
    
    if (error instanceof ApiHttpError && error.status === 404) {
      throw new ApiValidationError('No videos found in the provided URL')
    }
    
    throw error
  }
}

/**
 * Creates a new bulk transcription job
 * @param request - Bulk job creation request
 * @returns Promise<BulkJobResponse>
 */
export async function createBulkJob(
  request: BulkCreateRequest
): Promise<BulkJobResponse> {
  // Validate required parameters
  if (!request.url || typeof request.url !== 'string') {
    throw new ApiValidationError('URL is required and must be a string')
  }
  
  if (!request.transcript_method) {
    throw new ApiValidationError('Transcript method is required')
  }
  
  if (!['unofficial', 'groq', 'openai'].includes(request.transcript_method)) {
    throw new ApiValidationError('Invalid transcript method')
  }
  
  if (!['txt', 'srt', 'vtt', 'json'].includes(request.output_format)) {
    throw new ApiValidationError('Invalid output format')
  }

  try {
    const response = await bulkApiRequest<BulkJobResponse>('/api/v1/bulk/create', {
      method: 'POST',
      body: JSON.stringify(request),
    })

    return response
  } catch (error) {
    if (error instanceof ApiHttpError && error.status === 422) {
      throw new ApiValidationError(
        'Validation error: Invalid request parameters',
        error.response?.details
      )
    }
    
    if (error instanceof ApiHttpError && error.status === 403) {
      throw new ApiValidationError(
        'Rate limit exceeded or insufficient permissions for your tier'
      )
    }
    
    throw error
  }
}

/**
 * Gets the status of a bulk job
 * @param jobId - The job ID to check
 * @returns Promise<BulkJobResponse>
 */
export async function getBulkJobStatus(jobId: string): Promise<BulkJobResponse> {
  if (!jobId || typeof jobId !== 'string') {
    throw new ApiValidationError('Job ID is required and must be a string')
  }

  return await bulkApiRequest<BulkJobResponse>(`/api/v1/bulk/jobs/${jobId}`)
}

/**
 * Lists bulk jobs for the authenticated user
 * @param page - Page number (default: 1)
 * @param perPage - Items per page (default: 20)
 * @param status - Optional status filter
 * @returns Promise<BulkJobListResponse>
 */
export async function listBulkJobs(
  page: number = 1,
  perPage: number = 20,
  status?: JobStatus
): Promise<BulkJobListResponse> {
  const params = new URLSearchParams({
    page: page.toString(),
    per_page: perPage.toString(),
    ...(status && { status }),
  })

  return await bulkApiRequest<BulkJobListResponse>(
    `/api/v1/bulk/jobs?${params.toString()}`
  )
}

/**
 * Starts processing a bulk job
 * @param jobId - The job ID to start
 * @returns Promise with start confirmation
 */
export async function startBulkJob(jobId: string): Promise<{
  status: string
  job_id: string
  message: string
  total_videos: number
}> {
  if (!jobId || typeof jobId !== 'string') {
    throw new ApiValidationError('Job ID is required and must be a string')
  }

  return await bulkApiRequest(`/api/v1/bulk/jobs/${jobId}/start`, {
    method: 'POST',
  })
}

/**
 * Cancels a bulk job
 * @param jobId - The job ID to cancel
 * @returns Promise with cancellation confirmation
 */
export async function cancelBulkJob(jobId: string): Promise<{
  status: string
  job_id: string
  message: string
  completed_videos: number
}> {
  if (!jobId || typeof jobId !== 'string') {
    throw new ApiValidationError('Job ID is required and must be a string')
  }

  return await bulkApiRequest(`/api/v1/bulk/jobs/${jobId}/cancel`, {
    method: 'POST',
  })
}

/**
 * Downloads the ZIP file of completed transcripts for a bulk job
 * @param jobId - The job ID to download
 * @returns Promise<Blob> - ZIP file blob
 */
export async function downloadBulkJobResults(jobId: string): Promise<Blob> {
  if (!jobId || typeof jobId !== 'string') {
    throw new ApiValidationError('Job ID is required and must be a string')
  }

  const url = `${getApiUrl()}/api/v1/bulk/jobs/${jobId}/download`
  
  try {
    const headers = await createHeaders(false);
    const response = await fetch(url, {
      headers,
    })
    
    if (!response.ok) {
      let errorData: any
      try {
        errorData = await response.json()
      } catch {
        errorData = { error: 'Download failed', message: response.statusText }
      }
      
      throw new ApiHttpError(
        errorData.message || `HTTP ${response.status}: ${response.statusText}`,
        response.status,
        response.statusText,
        errorData
      )
    }

    return await response.blob()
  } catch (error) {
    if (error instanceof ApiHttpError) {
      throw error
    }
    
    throw new ApiNetworkError(
      `Download failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      error instanceof Error ? error : undefined
    )
  }
}

/**
 * Deletes a bulk job and all its data
 * @param jobId - The job ID to delete
 * @returns Promise with deletion confirmation
 */
export async function deleteBulkJob(jobId: string): Promise<{
  status: string
  job_id: string
  message: string
}> {
  if (!jobId || typeof jobId !== 'string') {
    throw new ApiValidationError('Job ID is required and must be a string')
  }

  return await bulkApiRequest(`/api/v1/bulk/jobs/${jobId}`, {
    method: 'DELETE',
  }, true)
}

/**
 * Helper function to validate playlist/channel URLs
 * @param url - URL to validate
 * @returns boolean indicating if URL is valid
 */
export function isValidBulkUrl(url: string): boolean {
  if (!url || typeof url !== 'string') return false
  
  const playlistRegex = /(?:youtube\.com\/(?:playlist\?list=|watch\?v=.*&list=))([\w-]+)/
  const channelRegex = /(?:youtube\.com\/(?:@[\w-]+|c\/[\w-]+|channel\/[\w-]+|user\/[\w-]+))/
  
  return playlistRegex.test(url) || channelRegex.test(url)
}

/**
 * Helper function to extract source type from URL
 * @param url - YouTube URL
 * @returns 'playlist' | 'channel' | 'unknown'
 */
export function getBulkSourceType(url: string): 'playlist' | 'channel' | 'unknown' {
  if (!url) return 'unknown'
  
  if (url.includes('playlist?list=') || url.includes('&list=')) {
    return 'playlist'
  }
  
  if (url.includes('/@') || url.includes('/c/') || url.includes('/channel/') || url.includes('/user/')) {
    return 'channel'
  }
  
  return 'unknown'
}

/**
 * Helper function to format duration from seconds to human readable
 * @param seconds - Duration in seconds
 * @returns Formatted duration string
 */
export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

/**
 * Helper function to format file size
 * @param bytes - Size in bytes
 * @returns Formatted size string
 */
export function formatFileSize(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

// Export types and utilities for use in components
export type {
  TranscriptMethod,
  OutputFormat,
  JobStatus,
  TaskStatus,
  BulkAnalyzeRequest,
  BulkCreateRequest,
  VideoInfo,
  BulkAnalyzeResponse,
  BulkTaskResponse,
  BulkJobResponse,
  BulkJobListResponse,
  BulkError,
}

export const BulkApiErrors = {
  ApiNetworkError,
  ApiHttpError,
  ApiValidationError,
}

// Export downloadJobResults from api.ts for convenience
export { downloadJobResults } from './api'