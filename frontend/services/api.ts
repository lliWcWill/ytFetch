/**
 * API Service Layer for YouTube Transcription
 * Provides type-safe interfaces and functions for interacting with the transcription API
 */

// TypeScript Interfaces

export type TranscriptionMethod = 'unofficial' | 'groq';
export type OutputFormat = 'txt' | 'srt' | 'vtt' | 'json';

export interface TranscribeRequest {
  url: string;
  client_id: string;
  method: TranscriptionMethod;
  output_format?: OutputFormat;
  language?: string;
}

export interface TranscribeResponse {
  job_id: string;
  websocket_url: string;
  status: string;
}

export interface VideoMetadata {
  title: string;
  duration: number;
  uploader: string;
  upload_date?: string;
  view_count?: number;
  description?: string;
  thumbnail_url?: string;
  video_id: string;
}

export interface ProcessingMetadata {
  processing_time: number;
  download_time: number;
  transcription_time?: number;
  file_size?: number;
  audio_format?: string;
  model_used?: string;
}

export interface ApiError {
  error: string;
  message: string;
  status_code: number;
  details?: Record<string, any>;
}

export interface ApiResponse<T> {
  data?: T;
  error?: ApiError;
  success: boolean;
}

// Custom Error Classes

export class ApiNetworkError extends Error {
  constructor(message: string, public cause?: Error) {
    super(message);
    this.name = 'ApiNetworkError';
  }
}

export class ApiHttpError extends Error {
  constructor(
    message: string,
    public status: number,
    public statusText: string,
    public response?: any
  ) {
    super(message);
    this.name = 'ApiHttpError';
  }
}

export class ApiValidationError extends Error {
  constructor(message: string, public validationErrors?: Record<string, string[]>) {
    super(message);
    this.name = 'ApiValidationError';
  }
}

// Utility Functions

/**
 * Generates a unique client ID using UUID v4
 * Follows RFC 4122 standard for UUID v4 generation
 */
export function generateClientId(): string {
  // UUID v4 implementation with proper random number generation
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    // Use native crypto.randomUUID if available (modern browsers)
    return crypto.randomUUID();
  }
  
  // Fallback implementation for older browsers
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

/**
 * Gets the API base URL from environment variables with fallback
 */
export function getApiUrl(): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) {
    console.warn('NEXT_PUBLIC_API_URL not set, using default localhost:8000');
    return 'http://localhost:8000';
  }
  return apiUrl;
}

/**
 * Creates headers for API requests with authentication
 */
async function createHeaders(includeContentType = true): Promise<Record<string, string>> {
  const { createAuthHeaders } = await import('@/lib/auth-token');
  return await createAuthHeaders(includeContentType);
}

/**
 * Handles fetch responses with proper error handling and type safety
 */
async function handleResponse<T>(response: Response): Promise<T> {
  // Handle 401 Unauthorized - redirect to login
  if (response.status === 401) {
    const { handleAuthError } = await import('@/lib/auth-token');
    handleAuthError();
    throw new ApiHttpError('Authentication required', 401, 'Unauthorized', null);
  }

  // Check if response is ok
  if (!response.ok) {
    let errorData: any;
    try {
      errorData = await response.json();
    } catch {
      errorData = { error: 'Unknown error', message: response.statusText };
    }
    
    throw new ApiHttpError(
      errorData.message || `HTTP ${response.status}: ${response.statusText}`,
      response.status,
      response.statusText,
      errorData
    );
  }

  // Parse JSON response
  try {
    const data = await response.json();
    return data as T;
  } catch (error) {
    throw new Error(`Failed to parse JSON response: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Makes a typed API request with error handling
 */
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${getApiUrl()}${endpoint}`;
  
  try {
    const defaultHeaders = await createHeaders();
    const response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    });
    
    return await handleResponse<T>(response);
  } catch (error) {
    if (error instanceof ApiHttpError) {
      throw error;
    }
    
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ApiNetworkError(
        `Network error: Unable to connect to ${url}`,
        error
      );
    }
    
    throw new ApiNetworkError(
      `Request failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      error instanceof Error ? error : undefined
    );
  }
}

// Main API Functions

/**
 * Starts a transcription job for a YouTube video
 * @param url - YouTube video URL
 * @param clientId - Unique client identifier (UUID v4)
 * @param options - Optional transcription parameters including method, output_format, and language
 * @returns Promise<TranscribeResponse>
 */
export async function startTranscriptionJob(
  url: string,
  clientId: string,
  options?: {
    output_format?: OutputFormat;
    language?: string;
    method?: TranscriptionMethod;
  }
): Promise<TranscribeResponse> {
  // Validate required parameters
  if (!url || typeof url !== 'string') {
    throw new ApiValidationError('URL is required and must be a string');
  }
  
  if (!clientId || typeof clientId !== 'string') {
    throw new ApiValidationError('Client ID is required and must be a string');
  }

  const method = options?.method || 'groq';
  if (method !== 'unofficial' && method !== 'groq') {
    throw new ApiValidationError('Method must be either "unofficial" or "groq"');
  }
  
  // URL validation (basic YouTube URL check)
  const youtubeRegex = /^https?:\/\/(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)/;
  if (!youtubeRegex.test(url)) {
    throw new ApiValidationError('Invalid YouTube URL format');
  }

  const requestData: TranscribeRequest = {
    url,
    client_id: clientId,
    method,
    output_format: options?.output_format || 'txt',
    ...options,
  };

  try {
    const response = await apiRequest<TranscribeResponse>('/api/v1/transcribe', {
      method: 'POST',
      body: JSON.stringify(requestData),
    });

    return response;
  } catch (error) {
    if (error instanceof ApiHttpError && error.status === 422) {
      throw new ApiValidationError(
        'Validation error: Invalid request parameters',
        error.response?.details
      );
    }
    
    // Handle method-specific errors
    if (error instanceof ApiHttpError && error.status === 400) {
      if (error.response?.details?.includes('groq')) {
        throw new ApiValidationError(
          'Groq transcription error: Check API key configuration or try unofficial method'
        );
      }
      if (error.response?.details?.includes('unofficial')) {
        throw new ApiValidationError(
          'Unofficial transcription error: Video may not have auto-generated captions or try groq method'
        );
      }
    }
    
    throw error;
  }
}

/**
 * Gets the status of a transcription job
 * @param jobId - The job ID to check
 * @returns Promise with job status information
 */
export async function getJobStatus(jobId: string): Promise<{
  job_id: string;
  status: string;
  progress?: number;
  error?: string;
  result?: any;
}> {
  if (!jobId || typeof jobId !== 'string') {
    throw new ApiValidationError('Job ID is required and must be a string');
  }

  return await apiRequest(`/api/v1/transcribe/${jobId}/status`);
}

/**
 * Cancels a transcription job
 * @param jobId - The job ID to cancel
 * @returns Promise with cancellation confirmation
 */
export async function cancelJob(jobId: string): Promise<{
  job_id: string;
  status: string;
  message: string;
}> {
  if (!jobId || typeof jobId !== 'string') {
    throw new ApiValidationError('Job ID is required and must be a string');
  }

  return await apiRequest(`/api/v1/transcribe/${jobId}/cancel`, {
    method: 'POST',
  });
}

/**
 * Gets video metadata for a YouTube URL
 * @param url - YouTube video URL
 * @returns Promise<VideoMetadata>
 */
export async function getVideoMetadata(url: string): Promise<VideoMetadata> {
  if (!url || typeof url !== 'string') {
    throw new ApiValidationError('URL is required and must be a string');
  }

  const youtubeRegex = /^https?:\/\/(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)/;
  if (!youtubeRegex.test(url)) {
    throw new ApiValidationError('Invalid YouTube URL format');
  }

  return await apiRequest(`/api/v1/video/metadata?url=${encodeURIComponent(url)}`);
}

/**
 * Health check for the API
 * @returns Promise with API health status
 */
export async function healthCheck(): Promise<{
  status: string;
  version: string;
  uptime: number;
}> {
  return await apiRequest('/api/v1/health');
}

/**
 * Downloads the ZIP file of completed transcripts for a bulk job
 * @param jobId - The job ID to download
 * @returns Promise<void>
 */
export async function downloadJobResults(jobId: string): Promise<void> {
  if (!jobId || typeof jobId !== 'string') {
    throw new ApiValidationError('Job ID is required and must be a string');
  }

  const url = `${getApiUrl()}/api/v1/bulk/jobs/${jobId}/download`;
  
  try {
    const headers = await createHeaders(false);
    const response = await fetch(url, {
      headers,
    });
    
    if (!response.ok) {
      let errorData: any;
      try {
        errorData = await response.json();
      } catch {
        errorData = { error: 'Download failed', message: response.statusText };
      }
      
      throw new ApiHttpError(
        errorData.message || `HTTP ${response.status}: ${response.statusText}`,
        response.status,
        response.statusText,
        errorData
      );
    }

    // Get the blob
    const blob = await response.blob();
    
    // Create temporary URL
    const downloadUrl = URL.createObjectURL(blob);
    
    // Create temporary anchor element and trigger download
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `job-${jobId}-transcripts.zip`;
    document.body.appendChild(link);
    link.click();
    
    // Clean up
    document.body.removeChild(link);
    URL.revokeObjectURL(downloadUrl);
  } catch (error) {
    if (error instanceof ApiHttpError) {
      throw error;
    }
    
    throw new ApiNetworkError(
      `Download failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      error instanceof Error ? error : undefined
    );
  }
}

/**
 * Creates a transcription request with sensible defaults
 * @param url - YouTube video URL
 * @param method - Transcription method
 * @param options - Optional parameters
 * @returns Complete transcription request object
 */
export function createTranscriptionRequest(
  url: string,
  method: TranscriptionMethod,
  options?: {
    output_format?: OutputFormat;
    language?: string;
    client_id?: string;
  }
): TranscribeRequest {
  return {
    url,
    client_id: options?.client_id || generateClientId(),
    method,
    output_format: options?.output_format || 'txt',
    ...(options?.language && { language: options.language }),
  };
}

// Export types and utilities for use in components
export type {
  TranscriptionMethod,
  OutputFormat,
  TranscribeRequest,
  TranscribeResponse,
  VideoMetadata,
  ProcessingMetadata,
  ApiError,
  ApiResponse,
};

export const ApiErrors = {
  ApiNetworkError,
  ApiHttpError,
  ApiValidationError,
};