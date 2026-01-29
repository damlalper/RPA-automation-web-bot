import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, Clock, RefreshCw } from 'lucide-react'
import clsx from 'clsx'
import { tasksApi } from '../services/api'
import { formatDistanceToNow, format } from 'date-fns'

export default function TaskDetail() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()

  const { data: task, isLoading } = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => tasksApi.get(taskId!),
    enabled: !!taskId,
    refetchInterval: 5000,
  })

  const { data: taskData } = useQuery({
    queryKey: ['task-data', taskId],
    queryFn: () => tasksApi.getData(taskId!),
    enabled: !!taskId && task?.data?.status === 'success',
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-slate-400 animate-spin" />
      </div>
    )
  }

  if (!task?.data) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-600">Task not found</p>
      </div>
    )
  }

  const t = task.data

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/tasks')}
          className="p-2 hover:bg-slate-100 rounded-lg"
        >
          <ArrowLeft className="w-5 h-5 text-slate-600" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">{t.name}</h1>
          <p className="text-slate-600">{t.target_url}</p>
        </div>
        <span
          className={clsx(
            'px-3 py-1 rounded-full text-sm font-medium',
            t.status === 'success' && 'bg-green-100 text-green-700',
            t.status === 'failed' && 'bg-red-100 text-red-700',
            t.status === 'running' && 'bg-blue-100 text-blue-700',
            t.status === 'pending' && 'bg-yellow-100 text-yellow-700'
          )}
        >
          {t.status}
        </span>
      </div>

      {/* Info Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-sm text-slate-600">Items Scraped</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">
            {t.items_scraped}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-sm text-slate-600">Duration</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">
            {t.duration ? `${t.duration.toFixed(2)}s` : '-'}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-sm text-slate-600">Retries</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">
            {t.retry_count} / {t.max_retries}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-sm text-slate-600">Priority</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{t.priority}</p>
        </div>
      </div>

      {/* Timeline */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Timeline</h3>
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
              <Clock className="w-5 h-5 text-slate-600" />
            </div>
            <div>
              <p className="font-medium text-slate-900">Created</p>
              <p className="text-sm text-slate-600">
                {t.created_at
                  ? format(new Date(t.created_at), 'PPpp')
                  : '-'}
              </p>
            </div>
          </div>
          {t.started_at && (
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                <RefreshCw className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="font-medium text-slate-900">Started</p>
                <p className="text-sm text-slate-600">
                  {format(new Date(t.started_at), 'PPpp')}
                </p>
              </div>
            </div>
          )}
          {t.completed_at && (
            <div className="flex items-center gap-4">
              <div
                className={clsx(
                  'w-10 h-10 rounded-full flex items-center justify-center',
                  t.status === 'success' ? 'bg-green-100' : 'bg-red-100'
                )}
              >
                <Clock
                  className={clsx(
                    'w-5 h-5',
                    t.status === 'success' ? 'text-green-600' : 'text-red-600'
                  )}
                />
              </div>
              <div>
                <p className="font-medium text-slate-900">Completed</p>
                <p className="text-sm text-slate-600">
                  {format(new Date(t.completed_at), 'PPpp')}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Error Message */}
      {t.error_message && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <h3 className="font-semibold text-red-900 mb-2">Error</h3>
          <p className="text-red-700 font-mono text-sm">{t.error_message}</p>
        </div>
      )}

      {/* Scraped Data */}
      {taskData?.data?.data && taskData.data.data.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">
            Scraped Data ({taskData.data.total} items)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  {Object.keys(
                    taskData.data.data[0]?.cleaned_data ||
                      taskData.data.data[0]?.raw_data ||
                      {}
                  ).map((key) => (
                    <th
                      key={key}
                      className="text-left py-2 px-3 font-medium text-slate-600"
                    >
                      {key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {taskData.data.data.slice(0, 10).map((item: any, i: number) => {
                  const data = item.cleaned_data || item.raw_data || {}
                  return (
                    <tr key={i} className="border-b border-slate-100">
                      {Object.values(data).map((value: any, j) => (
                        <td
                          key={j}
                          className="py-2 px-3 text-slate-700 max-w-xs truncate"
                        >
                          {String(value)}
                        </td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
