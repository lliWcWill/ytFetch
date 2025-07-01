'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/utils/supabase/client'
import { Trash2, Clock, CheckCircle, AlertCircle } from 'lucide-react'

interface CleanupHistory {
  executed_at: string
  stuck_jobs_cleaned: number
  expired_guest_sessions: number
  execution_time_ms: number
  error_message?: string
}

export function CleanupMonitor() {
  const [history, setHistory] = useState<CleanupHistory[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)

  const fetchHistory = async () => {
    const supabase = createClient()
    
    const { data, error } = await supabase
      .rpc('get_cleanup_history', { limit_rows: 10 })
    
    if (!error && data) {
      setHistory(data)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchHistory()
  }, [])

  const runManualCleanup = async () => {
    setRunning(true)
    const supabase = createClient()
    
    try {
      const { data, error } = await supabase.rpc('manual_cleanup_trigger')
      
      if (!error) {
        // Refresh history
        await fetchHistory()
        alert('Cleanup completed successfully!')
      } else {
        alert(`Cleanup failed: ${error.message}`)
      }
    } catch (err) {
      alert('Failed to run cleanup')
    } finally {
      setRunning(false)
    }
  }

  if (loading) return <div>Loading cleanup history...</div>

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold">Cleanup Monitor</h2>
        <button
          onClick={runManualCleanup}
          disabled={running}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          <Trash2 size={16} />
          {running ? 'Running...' : 'Run Manual Cleanup'}
        </button>
      </div>

      <div className="space-y-3">
        {history.length === 0 ? (
          <p className="text-gray-500">No cleanup history yet</p>
        ) : (
          history.map((record, idx) => (
            <div
              key={idx}
              className={`p-3 rounded border ${
                record.error_message ? 'border-red-200 bg-red-50' : 'border-gray-200'
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    {record.error_message ? (
                      <AlertCircle className="text-red-500" size={16} />
                    ) : (
                      <CheckCircle className="text-green-500" size={16} />
                    )}
                    <span className="font-medium">
                      {new Date(record.executed_at).toLocaleString()}
                    </span>
                  </div>
                  {record.error_message ? (
                    <p className="text-red-600 text-sm mt-1">{record.error_message}</p>
                  ) : (
                    <div className="text-sm text-gray-600 mt-1">
                      <span className="mr-3">
                        Jobs cleaned: {record.stuck_jobs_cleaned}
                      </span>
                      <span className="mr-3">
                        Guest sessions: {record.expired_guest_sessions}
                      </span>
                      <span className="flex items-center gap-1 inline-flex">
                        <Clock size={12} />
                        {record.execution_time_ms}ms
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="mt-4 text-sm text-gray-500">
        <p>Automatic cleanup runs:</p>
        <ul className="list-disc list-inside">
          <li>Daily at 2:00 AM UTC</li>
          <li>Weekly on Sundays at 3:00 AM UTC</li>
        </ul>
      </div>
    </div>
  )
}