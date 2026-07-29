import { useState, useEffect } from 'react'
import * as api from './api'
import ErrorBoundary from './components/ErrorBoundary'
import AuthScreen from './components/AuthScreen'
import Dashboard from './components/Dashboard'
import AccountSettings from './components/AccountSettings'

export default function App() {
  const [authed, setAuthed] = useState(null)
  const [user, setUser] = useState(null)
  const [view, setView] = useState('dashboard')

  useEffect(() => {
    if (api.isAuthenticated()) {
      api.getMe()
        .then(u => { setUser(u); setAuthed(true) })
        .catch(() => { api.clearToken(); setAuthed(false) })
    } else {
      setAuthed(false)
    }
  }, [])

  const handleAuth = (res) => {
    setUser({ email: res.email, ...res })
    setAuthed(true)
  }

  const handleLogout = () => {
    api.clearToken()
    setAuthed(false)
    setUser(null)
  }

  if (authed === null) {
    return (
      <div className="loading-screen">
        <div className="loader" />
        <p>Cargando...</p>
      </div>
    )
  }

  if (!authed || !user) {
    return <AuthScreen onAuth={handleAuth} />
  }

  return (
    <ErrorBoundary>
      <div className="app">
        {view === 'account' ? (
          <AccountSettings user={user} onBack={() => setView('dashboard')} />
        ) : (
          <Dashboard user={user} onLogout={handleLogout} onAccount={() => setView('account')} />
        )}
      </div>
    </ErrorBoundary>
  )
}
