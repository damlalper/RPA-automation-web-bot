import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Types
export interface Task {
  id: string
  name: string
  task_type: string
  status: string
  target_url: string
  config: Record<string, unknown> | null
  retry_count: number
  max_retries: number
  priority: number
  created_at: string | null
  started_at: string | null
  completed_at: string | null
  duration: number | null
  error_message: string | null
  items_scraped: number
  worker_id: string | null
}

export interface TaskCreateData {
  name: string
  target_url: string
  task_type?: string
  config?: Record<string, unknown>
  selectors?: Record<string, unknown>
  priority?: number
  max_retries?: number
}

export interface TaskListResponse {
  tasks: Task[]
  total: number
  page: number
  page_size: number
}

export interface TaskStats {
  total: number
  by_status: Record<string, number>
  success_rate: number
  avg_duration: number | null
}

export interface MetricsSummary {
  tasks: TaskStats
  proxies: {
    total: number
    healthy: number
    unhealthy: number
    avg_response_time: number | null
    total_requests: number
    success_rate: number
  }
  performance: {
    total: number
    success_count: number
    fail_count: number
    success_rate: number
    avg_duration: number | null
  }
  timestamp: string
}

export interface HealthStatus {
  status: string
  timestamp: string
  version: string
  environment: string
  components: Record<string, { status: string; message?: string }>
}

// API Functions
export const healthApi = {
  check: () => api.get<HealthStatus>('/health'),
  info: () => api.get('/info'),
}

export const tasksApi = {
  list: (params?: { status?: string; page?: number; page_size?: number }) =>
    api.get<TaskListResponse>('/tasks', { params }),

  get: (taskId: string) => api.get<Task>(`/tasks/${taskId}`),

  create: (data: TaskCreateData) => api.post<Task>('/tasks', data),

  update: (taskId: string, data: Partial<TaskCreateData>) =>
    api.put<Task>(`/tasks/${taskId}`, data),

  delete: (taskId: string) => api.delete(`/tasks/${taskId}`),

  cancel: (taskId: string) => api.post<Task>(`/tasks/${taskId}/cancel`),

  retry: (taskId: string) => api.post<Task>(`/tasks/${taskId}/retry`),

  getData: (taskId: string, params?: { page?: number; page_size?: number }) =>
    api.get(`/tasks/${taskId}/data`, { params }),

  stats: () => api.get<TaskStats>('/tasks/stats'),
}

export const metricsApi = {
  summary: () => api.get<MetricsSummary>('/metrics/summary'),

  tasks: (hours?: number) => api.get('/metrics/tasks', { params: { hours } }),

  proxies: () => api.get('/metrics/proxies'),

  proxyList: (activeOnly?: boolean) =>
    api.get('/metrics/proxies/list', { params: { active_only: activeOnly } }),

  performance: (metricType?: string, hours?: number) =>
    api.get('/metrics/performance', { params: { metric_type: metricType, hours } }),
}

export default api
