import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './components/Dashboard'
import TaskList from './components/TaskList'
import TaskDetail from './components/TaskDetail'
import Metrics from './components/Metrics'
import Proxies from './components/Proxies'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="tasks" element={<TaskList />} />
          <Route path="tasks/:taskId" element={<TaskDetail />} />
          <Route path="metrics" element={<Metrics />} />
          <Route path="proxies" element={<Proxies />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
