import { useQuery } from '@tanstack/react-query'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts'
import { metricsApi } from '../services/api'

export default function Metrics() {
  const { data: summary } = useQuery({
    queryKey: ['metrics-summary'],
    queryFn: () => metricsApi.summary(),
    refetchInterval: 10000,
  })

  const { data: performance } = useQuery({
    queryKey: ['metrics-performance'],
    queryFn: () => metricsApi.performance('scraping', 24),
    refetchInterval: 10000,
  })

  const metrics = summary?.data

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Metrics</h1>
        <p className="text-slate-600">Performance and usage analytics</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <p className="text-sm text-slate-600">Total Tasks</p>
          <p className="text-3xl font-bold text-slate-900 mt-2">
            {metrics?.tasks?.total || 0}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <p className="text-sm text-slate-600">Success Rate</p>
          <p className="text-3xl font-bold text-green-600 mt-2">
            {metrics?.tasks?.success_rate?.toFixed(1) || 0}%
          </p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <p className="text-sm text-slate-600">Proxy Success Rate</p>
          <p className="text-3xl font-bold text-blue-600 mt-2">
            {metrics?.proxies?.success_rate?.toFixed(1) || 0}%
          </p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <p className="text-sm text-slate-600">Avg Response Time</p>
          <p className="text-3xl font-bold text-slate-900 mt-2">
            {metrics?.proxies?.avg_response_time
              ? `${(metrics.proxies.avg_response_time * 1000).toFixed(0)}ms`
              : 'N/A'}
          </p>
        </div>
      </div>

      {/* Task Status Breakdown */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">
          Task Status Breakdown
        </h3>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={
                metrics?.tasks?.by_status
                  ? Object.entries(metrics.tasks.by_status).map(
                      ([name, value]) => ({ name, value })
                    )
                  : []
              }
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Performance Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">
            Scraping Performance (24h)
          </h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-slate-600">Total Operations</span>
              <span className="font-semibold">
                {metrics?.performance?.total || 0}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-600">Successful</span>
              <span className="font-semibold text-green-600">
                {metrics?.performance?.success_count || 0}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-600">Failed</span>
              <span className="font-semibold text-red-600">
                {metrics?.performance?.fail_count || 0}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-600">Avg Duration</span>
              <span className="font-semibold">
                {metrics?.performance?.avg_duration
                  ? `${metrics.performance.avg_duration.toFixed(2)}s`
                  : 'N/A'}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">
            Proxy Statistics
          </h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-slate-600">Total Proxies</span>
              <span className="font-semibold">
                {metrics?.proxies?.total || 0}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-600">Healthy</span>
              <span className="font-semibold text-green-600">
                {metrics?.proxies?.healthy || 0}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-600">Unhealthy</span>
              <span className="font-semibold text-red-600">
                {metrics?.proxies?.unhealthy || 0}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-600">Total Requests</span>
              <span className="font-semibold">
                {metrics?.proxies?.total_requests || 0}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
