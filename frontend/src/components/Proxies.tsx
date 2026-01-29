import { useQuery } from '@tanstack/react-query'
import { Shield, CheckCircle, XCircle, Clock, Zap } from 'lucide-react'
import clsx from 'clsx'
import { metricsApi } from '../services/api'

export default function Proxies() {
  const { data: proxyStats } = useQuery({
    queryKey: ['proxy-stats'],
    queryFn: () => metricsApi.proxies(),
    refetchInterval: 30000,
  })

  const { data: proxyList } = useQuery({
    queryKey: ['proxy-list'],
    queryFn: () => metricsApi.proxyList(),
    refetchInterval: 30000,
  })

  const stats = proxyStats?.data
  const proxies = proxyList?.data?.proxies || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Proxies</h1>
        <p className="text-slate-600">Manage and monitor proxy pool</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary-50 flex items-center justify-center">
              <Shield className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <p className="text-sm text-slate-600">Total Proxies</p>
              <p className="text-2xl font-bold text-slate-900">
                {stats?.total || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
              <CheckCircle className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-slate-600">Healthy</p>
              <p className="text-2xl font-bold text-green-600">
                {stats?.healthy || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center">
              <Clock className="w-5 h-5 text-slate-600" />
            </div>
            <div>
              <p className="text-sm text-slate-600">Avg Response</p>
              <p className="text-2xl font-bold text-slate-900">
                {stats?.avg_response_time
                  ? `${(stats.avg_response_time * 1000).toFixed(0)}ms`
                  : 'N/A'}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
              <Zap className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-slate-600">Success Rate</p>
              <p className="text-2xl font-bold text-blue-600">
                {stats?.success_rate?.toFixed(1) || 0}%
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Proxy List */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h3 className="text-lg font-semibold text-slate-900">Proxy List</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                  Address
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                  Status
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                  Response Time
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                  Success Rate
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                  Requests
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600">
                  Country
                </th>
              </tr>
            </thead>
            <tbody>
              {proxies.map((proxy: any, index: number) => (
                <tr key={index} className="border-t border-slate-100">
                  <td className="py-3 px-4">
                    <span className="font-mono text-sm text-slate-700">
                      {proxy.address}:{proxy.port}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={clsx(
                        'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium',
                        proxy.is_healthy
                          ? 'bg-green-100 text-green-700'
                          : 'bg-red-100 text-red-700'
                      )}
                    >
                      {proxy.is_healthy ? (
                        <>
                          <CheckCircle className="w-3 h-3" /> Healthy
                        </>
                      ) : (
                        <>
                          <XCircle className="w-3 h-3" /> Unhealthy
                        </>
                      )}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-600">
                    {proxy.response_time
                      ? `${(proxy.response_time * 1000).toFixed(0)}ms`
                      : '-'}
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={clsx(
                        'font-medium',
                        proxy.success_rate >= 80
                          ? 'text-green-600'
                          : proxy.success_rate >= 50
                          ? 'text-yellow-600'
                          : 'text-red-600'
                      )}
                    >
                      {proxy.success_rate?.toFixed(1) || 0}%
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-600">
                    {proxy.total_requests || 0}
                  </td>
                  <td className="py-3 px-4 text-slate-600">
                    {proxy.country || '-'}
                  </td>
                </tr>
              ))}
              {proxies.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400">
                    No proxies configured
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
