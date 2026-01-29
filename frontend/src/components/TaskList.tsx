import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Plus,
  RefreshCw,
  Trash2,
  XCircle,
  RotateCcw,
  ExternalLink,
} from 'lucide-react'
import clsx from 'clsx'
import { tasksApi, TaskCreateData } from '../services/api'
import { formatDistanceToNow } from 'date-fns'

export default function TaskList() {
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string>('')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['tasks', statusFilter],
    queryFn: () => tasksApi.list({ status: statusFilter || undefined }),
    refetchInterval: 5000,
  })

  const deleteMutation = useMutation({
    mutationFn: tasksApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const cancelMutation = useMutation({
    mutationFn: tasksApi.cancel,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const retryMutation = useMutation({
    mutationFn: tasksApi.retry,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const tasks = data?.data?.tasks || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Tasks</h1>
          <p className="text-slate-600">Manage your automation tasks</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => refetch()}
            className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            New Task
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {['', 'pending', 'running', 'success', 'failed'].map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              statusFilter === status
                ? 'bg-primary-100 text-primary-700'
                : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            )}
          >
            {status || 'All'}
          </button>
        ))}
      </div>

      {/* Task Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                Name
              </th>
              <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                Status
              </th>
              <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                URL
              </th>
              <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                Items
              </th>
              <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                Created
              </th>
              <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.id} className="border-t border-slate-100">
                <td className="py-3 px-4">
                  <Link
                    to={`/tasks/${task.id}`}
                    className="font-medium text-primary-600 hover:text-primary-700"
                  >
                    {task.name}
                  </Link>
                </td>
                <td className="py-3 px-4">
                  <span
                    className={clsx(
                      'px-2 py-1 rounded-full text-xs font-medium',
                      task.status === 'success' &&
                        'bg-green-100 text-green-700',
                      task.status === 'failed' && 'bg-red-100 text-red-700',
                      task.status === 'running' && 'bg-blue-100 text-blue-700',
                      task.status === 'pending' &&
                        'bg-yellow-100 text-yellow-700',
                      task.status === 'cancelled' &&
                        'bg-slate-100 text-slate-700'
                    )}
                  >
                    {task.status}
                  </span>
                </td>
                <td className="py-3 px-4">
                  <a
                    href={task.target_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-slate-600 hover:text-primary-600 flex items-center gap-1 max-w-xs truncate"
                  >
                    {task.target_url.replace(/^https?:\/\//, '').slice(0, 30)}
                    ...
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </td>
                <td className="py-3 px-4 text-slate-600">
                  {task.items_scraped}
                </td>
                <td className="py-3 px-4 text-slate-600">
                  {task.created_at
                    ? formatDistanceToNow(new Date(task.created_at), {
                        addSuffix: true,
                      })
                    : '-'}
                </td>
                <td className="py-3 px-4">
                  <div className="flex gap-2">
                    {task.status === 'pending' && (
                      <button
                        onClick={() => cancelMutation.mutate(task.id)}
                        className="p-1 text-slate-400 hover:text-yellow-600"
                        title="Cancel"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    )}
                    {task.status === 'failed' && (
                      <button
                        onClick={() => retryMutation.mutate(task.id)}
                        className="p-1 text-slate-400 hover:text-blue-600"
                        title="Retry"
                      >
                        <RotateCcw className="w-4 h-4" />
                      </button>
                    )}
                    {task.status !== 'running' && (
                      <button
                        onClick={() => deleteMutation.mutate(task.id)}
                        className="p-1 text-slate-400 hover:text-red-600"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {tasks.length === 0 && (
              <tr>
                <td colSpan={6} className="py-12 text-center text-slate-400">
                  {isLoading ? 'Loading...' : 'No tasks found'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CreateTaskModal onClose={() => setShowCreateModal(false)} />
      )}
    </div>
  )
}

function CreateTaskModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<TaskCreateData>({
    name: '',
    target_url: '',
    task_type: 'scrape',
    priority: 0,
    max_retries: 3,
  })

  const createMutation = useMutation({
    mutationFn: tasksApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      onClose()
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl p-6 w-full max-w-md">
        <h2 className="text-xl font-bold text-slate-900 mb-4">
          Create New Task
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Name
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Target URL
            </label>
            <input
              type="url"
              value={formData.target_url}
              onChange={(e) =>
                setFormData({ ...formData, target_url: e.target.value })
              }
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Priority
              </label>
              <input
                type="number"
                min="0"
                max="100"
                value={formData.priority}
                onChange={(e) =>
                  setFormData({ ...formData, priority: parseInt(e.target.value) })
                }
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Max Retries
              </label>
              <input
                type="number"
                min="0"
                max="10"
                value={formData.max_retries}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    max_retries: parseInt(e.target.value),
                  })
                }
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {createMutation.isPending ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
