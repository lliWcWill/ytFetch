/**
 * Bulk Job Recovery Service
 * Helps users recover incomplete bulk jobs
 */

import { createClient } from '@/utils/supabase/client'

interface IncompleteJob {
  job_id: string
  status: string
  total_videos: number
  completed_videos: number
  created_at: string
  can_resume: boolean
}

/**
 * Get user's incomplete bulk jobs
 */
export async function getIncompleteJobs(sessionId?: string): Promise<IncompleteJob[]> {
  const supabase = createClient()
  
  try {
    // Get current user
    const { data: { user } } = await supabase.auth.getUser()
    
    // Call the function with either user_id or session_id
    const { data, error } = await supabase.rpc('get_user_incomplete_jobs', {
      p_user_id: user?.id || null,
      p_session_id: sessionId || null
    })
    
    if (error) {
      console.error('Error fetching incomplete jobs:', error)
      return []
    }
    
    return data || []
  } catch (error) {
    console.error('Error in getIncompleteJobs:', error)
    return []
  }
}

/**
 * Resume an incomplete job
 */
export async function resumeBulkJob(jobId: string): Promise<boolean> {
  try {
    // Navigate to the job details page
    window.location.href = `/bulk/${jobId}`
    return true
  } catch (error) {
    console.error('Error resuming job:', error)
    return false
  }
}

/**
 * Cancel a stuck job
 */
export async function cancelBulkJob(jobId: string): Promise<boolean> {
  const supabase = createClient()
  
  try {
    const { error } = await supabase
      .from('bulk_jobs')
      .update({ 
        status: 'cancelled',
        error_message: 'Cancelled by user',
        updated_at: new Date().toISOString()
      })
      .eq('job_id', jobId)
    
    if (error) {
      console.error('Error cancelling job:', error)
      return false
    }
    
    return true
  } catch (error) {
    console.error('Error in cancelBulkJob:', error)
    return false
  }
}