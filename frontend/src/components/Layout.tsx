import { Outlet, Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LayoutDashboard,
  ListTodo,
  BarChart3,
  Shield,
  Settings,
  Activity,
} from 'lucide-react'
import clsx from 'clsx'
import { healthApi } from '../services/api'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Tasks', href: '/tasks', icon: ListTodo },
  { name: 'Metrics', href: '/metrics', icon: BarChart3 },
  { name: 'Proxies', href: '/proxies', icon: Shield },
]

export default function Layout() {
  const location = useLocation()

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.check(),
    refetchInterval: 30000,
  })

  const healthStatus = health?.data?.status || 'unknown'

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-slate-200">
        {/* Logo */}
        <div className="flex items-center gap-2 px-6 py-4 border-b border-slate-200">
          <Activity className="w-8 h-8 text-primary-600" />
          <span className="text-xl font-bold text-slate-900">RPAFlow</span>
        </div>

        {/* Navigation */}
        <nav className="px-4 py-4 space-y-1">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                )}
              >
                <item.icon className="w-5 h-5" />
                {item.name}
              </Link>
            )
          })}
        </nav>

        {/* Status Footer */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-slate-200">
          <div className="flex items-center gap-2">
            <span
              className={clsx(
                'w-2 h-2 rounded-full',
                healthStatus === 'healthy'
                  ? 'bg-green-500'
                  : healthStatus === 'degraded'
                  ? 'bg-yellow-500'
                  : 'bg-red-500'
              )}
            />
            <span className="text-sm text-slate-600">
              System: <span className="capitalize">{healthStatus}</span>
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="pl-64">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
