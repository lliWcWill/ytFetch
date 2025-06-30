import { useEffect } from 'react'
import { supabase } from '@/services/supabase'

interface RealtimePayload {
  schema: string
  table: string
  commit_timestamp: string
  eventType: 'INSERT' | 'UPDATE' | 'DELETE'
  new?: any
  old?: any
  errors?: any
}

type OnRecordUpdate = (record: any) => void

export function useSupabaseRealtime(
  channelName: string,
  onRecordUpdate: OnRecordUpdate
) {
  useEffect(() => {
    // Create the subscription
    const channel = supabase
      .channel(channelName)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'video_tasks'
        },
        (payload: RealtimePayload) => {
          if (payload.new) {
            onRecordUpdate(payload.new)
          }
        }
      )
      .subscribe()

    // Cleanup function - remove the channel subscription
    return () => {
      supabase.removeChannel(channel)
    }
  }, [channelName, onRecordUpdate])
}