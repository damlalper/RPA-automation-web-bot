import { useQuery } from '@tanstack/react-query'
import {
  CheckCircle,
  XCircle,
  Clock,
  Activity,
  Server,
  Zap,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import { metricsApi, tasksApi } from '../services/api'
import clsx from 'clsx'

const COLORS = ['#22c55e', '#ef4444', '#f59e0b', '#3b82f6', '#8b5cf6']

function StatCard({
  title,
  value,
  icon: Icon,
  color = 'primary',
  subtitle,
}: {
  title: string
  value: string | number
  icon: React.ElementType
  color?: string
  subtitle?: string
}) {
  const colorClasses = {
    primary: 'bg-primary-50 text-primary-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
    yellow: 'bg-yellow-50 text-yellow-600',
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-slate-600">{title}</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
          {subtitle && (
            <p className="text-sm text-slate-500 mt-1">{subtitle}</p>
          )}
        </div>
        <div
          className={clsx(
            'w-12 h-12 rounded-lg flex items-center justify-center',
            colorClasses[color as keyof typeof colorClasses] ||
              colorClasses.primary
          )}
        >
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['metrics-summary'],
    queryFn: () => metricsApi.summary(),
    refetchInterval: 10000,
  })

  const { data: recentTasks } = useQuery({
    queryKey: ['recent-tasks'],
    queryFn: () => tasksApi.list({ page_size: 5 }),
    refetchInterval: 10000,
  })

  const summary = metrics?.data

  const taskStatusData = summary?.tasks?.by_status
    ? Object.entries(summary.tasks.by_status).map(([name, value]) => ({
        name,
        value,
      }))
    : []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-slate-600">
          Overview of your RPA automation platform
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Tasks"
          value={summary?.tasks?.total || 0}
          icon={Activity}
          color="primary"
        />
        <StatCard
          title="Success Rate"
          value={`${summary?.tasks?.success_rate?.toFixed(1) || 0}%`}
          icon={CheckCircle}
          color="green"
        />
        <StatCard
          title="Active Proxies"
          value={`${summary?.proxies?.healthy || 0}/${summary?.proxies?.total || 0}`}
          icon={Server}
          color="yellow"
        />
        <StatCard
          title="Avg Duration"
          value={
            summary?.performance?.avg_duration
              ? `${summary.performance.avg_duration.toFixed(2)}s`
              : 'N/A'
          }
          icon={Zap}
          color="primary"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Task Status Pie Chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">
            Task Status Distribution
          </h3>
          {taskStatusData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={taskStatusData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {taskStatusData.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-slate-400">
              No task data available
            </div>
          )}
        </div>

        {/* Proxy Health */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">
            Proxy Health
          </h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center p-4 bg-green-50 rounded-lg">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <span className="font-medium text-green-900">Healthy</span>
              </div>
              <span className="text-2xl font-bold text-green-600">
                {summary?.proxies?.healthy || 0}
              </span>
            </div>
            <div className="flex justify-between items-center p-4 bg-red-50 rounded-lg">
              <div className="flex items-center gap-3">
                <XCircle className="w-5 h-5 text-red-600" />
                <span className="font-medium text-red-900">Unhealthy</span>
              </div>
              <span className="text-2xl font-bold text-red-600">
                {summary?.proxies?.unhealthy || 0}
              </span>
            </div>
            <div className="flex justify-between items-center p-4 bg-slate-50 rounded-lg">
              <div className="flex items-center gap-3">
                <Clock className="w-5 h-5 text-slate-600" />
                <span className="font-medium text-slate-900">
                  Avg Response Time
                </span>
              </div>
              <span className="text-2xl font-bold text-slate-600">
                {summary?.proxies?.avg_response_time
                  ? `${(summary.proxies.avg_response_time * 1000).toFixed(0)}ms`
                  : 'N/A'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Tasks */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">
          Recent Tasks
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                  Name
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                  Status
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                  Items
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                  Duration
                </th>
              </tr>
            </thead>
            <tbody>
              {recentTasks?.data?.tasks?.map((task) => (
                <tr key={task.id} className="border-b border-slate-100">
                  <td className="py-3 px-4">
                    <span className="font-medium text-slate-900">
                      {task.name}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={clsx(
                        'px-2 py-1 rounded-full text-xs font-medium',
                        task.status === 'success' &&
                          'bg-green-100 text-green-700',
                        task.status === 'failed' && 'bg-red-100 text-red-700',
                        task.status === 'running' &&
                          'bg-blue-100 text-blue-700',
                        task.status === 'pending' &&
                          'bg-yellow-100 text-yellow-700'
                      )}
                    >
                      {task.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-600">
                    {task.items_scraped}
                  </td>
                  <td className="py-3 px-4 text-slate-600">
                    {task.duration ? `${task.duration.toFixed(2)}s` : '-'}
                  </td>
                </tr>
              ))}
              {(!recentTasks?.data?.tasks ||
                recentTasks.data.tasks.length === 0) && (
                <tr>
                  <td
                    colSpan={4}
                    className="py-8 text-center text-slate-400"
                  >
                    No tasks yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
