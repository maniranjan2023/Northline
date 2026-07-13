import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/app-shell'
import { AdminPage } from '@/pages/AdminPage'
import { ChatPage } from '@/pages/ChatPage'

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  )
}
