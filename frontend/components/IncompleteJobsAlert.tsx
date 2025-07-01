'use client'

import { useEffect, useState } from 'react'
import { getIncompleteJobs, resumeBulkJob, cancelBulkJob } from '@/services/bulkJobRecovery'
import { AlertCircle, Play, X } from 'lucide-react'

interface IncompleteJob {
  job_id: string
  status: string
  total_videos: number
  completed_videos: number
  created_at: string
  can_resume: boolean
}

export function IncompleteJobsAlert({ sessionId }: { sessionId?: string }) {
  const [jobs, setJobs] = useState<IncompleteJob[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const checkJobs = async () => {
      const incompleteJobs = await getIncompleteJobs(sessionId)
      setJobs(incompleteJobs)
      setLoading(false)
    }
    checkJobs()
  }, [sessionId])

  const handleResume = (jobId: string) => {
    resumeBulkJob(jobId)
  }

  const handleCancel = async (jobId: string) => {
    if (confirm('Are you sure you want to cancel this job?')) {
      await cancelBulkJob(jobId)
      setJobs(jobs.filter(j => j.job_id !== jobId))
    }
  }

  if (loading || jobs.length === 0) return null

  return (
    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
      <div className="flex items-start gap-3">
        <AlertCircle className="text-yellow-600 mt-0.5" size={20} />
        <div className="flex-1">
          <h3 className="font-semibold text-yellow-900 mb-2">
            You have incomplete bulk jobs
          </h3>
          <div className="space-y-2">
            {jobs.map((job) => (
              <div
                key={job.job_id}
                className="bg-white rounded p-3 flex items-center justify-between"
              >
                <div>
                  <p className="text-sm font-medium">
                    {job.completed_videos}/{job.total_videos} videos completed
                  </p>
                  <p className="text-xs text-gray-500">
                    Status: {job.status} • Started {new Date(job.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex gap-2">
                  {job.can_resume && (
                    <button
                      onClick={() => handleResume(job.job_id)}
                      className="p-2 text-green-600 hover:bg-green-50 rounded"
                      title="Resume job"
                    >
                      <Play size={16} />
                    </button>
                  )}
                  <button
                    onClick={() => handleCancel(job.job_id)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded"
                    title="Cancel job"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}