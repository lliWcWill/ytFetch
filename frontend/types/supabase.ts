export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  public: {
    Tables: {
      bulk_jobs: {
        Row: {
          id: string
          status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
          total_urls: number
          processed_urls: number
          failed_urls: number
          progress_percentage: number
          created_at: string
          updated_at: string
          user_id: string | null
          error_message: string | null
          metadata: Json | null
        }
        Insert: {
          id?: string
          status?: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
          total_urls: number
          processed_urls?: number
          failed_urls?: number
          progress_percentage?: number
          created_at?: string
          updated_at?: string
          user_id?: string | null
          error_message?: string | null
          metadata?: Json | null
        }
        Update: {
          id?: string
          status?: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
          total_urls?: number
          processed_urls?: number
          failed_urls?: number
          progress_percentage?: number
          created_at?: string
          updated_at?: string
          user_id?: string | null
          error_message?: string | null
          metadata?: Json | null
        }
        Relationships: []
      }
      video_tasks: {
        Row: {
          id: string
          bulk_job_id: string
          url: string
          status: 'pending' | 'processing' | 'completed' | 'failed'
          title: string | null
          duration: number | null
          transcript: string | null
          error_message: string | null
          created_at: string
          updated_at: string
          progress_percentage: number
          metadata: Json | null
        }
        Insert: {
          id?: string
          bulk_job_id: string
          url: string
          status?: 'pending' | 'processing' | 'completed' | 'failed'
          title?: string | null
          duration?: number | null
          transcript?: string | null
          error_message?: string | null
          created_at?: string
          updated_at?: string
          progress_percentage?: number
          metadata?: Json | null
        }
        Update: {
          id?: string
          bulk_job_id?: string
          url?: string
          status?: 'pending' | 'processing' | 'completed' | 'failed'
          title?: string | null
          duration?: number | null
          transcript?: string | null
          error_message?: string | null
          created_at?: string
          updated_at?: string
          progress_percentage?: number
          metadata?: Json | null
        }
        Relationships: [
          {
            foreignKeyName: "video_tasks_bulk_job_id_fkey"
            columns: ["bulk_job_id"]
            isOneToOne: false
            referencedRelation: "bulk_jobs"
            referencedColumns: ["id"]
          }
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

export type BulkJob = Database['public']['Tables']['bulk_jobs']['Row']
export type VideoTask = Database['public']['Tables']['video_tasks']['Row']

export type BulkJobInsert = Database['public']['Tables']['bulk_jobs']['Insert']
export type VideoTaskInsert = Database['public']['Tables']['video_tasks']['Insert']

export type BulkJobUpdate = Database['public']['Tables']['bulk_jobs']['Update']
export type VideoTaskUpdate = Database['public']['Tables']['video_tasks']['Update']

// Real-time event types
export type RealtimeEvent<T = any> = {
  eventType: 'INSERT' | 'UPDATE' | 'DELETE'
  new: T
  old: T
  errors: any[]
  schema: string
  table: string
}

export type BulkJobRealtimeEvent = RealtimeEvent<BulkJob>
export type VideoTaskRealtimeEvent = RealtimeEvent<VideoTask>