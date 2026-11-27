const electronBackend = window.electronAPI && window.electronAPI.backendUrl
  ? `${window.electronAPI.backendUrl.replace(/\/+$/, '')}/api`
  : null
const BASE = electronBackend || '/api'

export function getToken() { return localStorage.getItem('token') }
export function getRefreshToken() { return localStorage.getItem('refresh_token') }

function authHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...options.headers,
    },
  })
  if (!res.ok) {
    let detail
    try {
      const err = await res.json()
      detail = err.detail
    } catch {}
    if (res.status === 401 && !path.startsWith('/auth/')) {
      clearToken()
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new Event('auth:unauthorized'))
      }
    }
    throw new Error(detail || `Error ${res.status}`)
  }
  return res.json()
}

export function setToken(t) { localStorage.setItem('token', t) }
export function clearToken() {
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
}
export function isAuthenticated() { return !!getToken() }

function storeAuth(res) {
  setToken(res.token)
  if (res.refresh_token) localStorage.setItem('refresh_token', res.refresh_token)
  return res
}

export function register(email, password) {
  return request('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  }).then(storeAuth)
}

export function login(email, password) {
  return request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  }).then(storeAuth)
}

export function logout() {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return Promise.resolve()
  return request('/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken }),
  }).catch(() => {})
}

export function getMe() {
  return request('/auth/me')
}

export function saveBinanceKeys(apiKey, apiSecret) {
  return request('/auth/keys', {
    method: 'POST',
    body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret }),
  })
}

export function getStatus() {
  return request('/status')
}

export function startBot() {
  return request('/start', { method: 'POST' })
}

export function stopBot() {
  return request('/stop', { method: 'POST' })
}

export function getTrades(limit = 5) {
  return request(`/trades?limit=${limit}`)
}

export function getUserProfile() {
  return request('/user/profile')
}

export function getUserConfig() {
  return request('/user/config')
}

export function updateUserConfig(data) {
  return request('/user/config', {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function getTradeStats() {
  return request('/trades/stats')
}

export function getRecentTrades(sinceId = 0) {
  return request(`/trades/recent?since_id=${sinceId}`)
}

export function getFundingStatus() {
  return request('/funding/status')
}

export function startFunding() {
  return request('/funding/start', { method: 'POST' })
}

export function stopFunding() {
  return request('/funding/stop', { method: 'POST' })
}

export function getRecentAlerts() {
  return request('/alerts/recent')
}

export function getKlines(symbol = 'BTCUSDT', interval = '1h', limit = 200) {
  return request(`/market/klines?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`)
}

export function suggestConfig() {
  return request('/config/suggest')
}

function getWsUrl() {
  if (electronBackend) {
    const origin = electronBackend.replace(/\/api$/, '')
    const proto = origin.startsWith('https') ? 'wss:' : 'ws:'
    const host = origin.replace(/^https?:\/\//, '')
    return `${proto}//${host}/api/ws`
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${proto}//${host}/api/ws`
}

let ws = null
let wsCallbacks = new Set()
let connectionListeners = new Set()
let reconnectTimer = null
let reconnectAttempts = 0
const MAX_RECONNECT_ATTEMPTS = 10
const BASE_RECONNECT_DELAY = 1000
const MAX_RECONNECT_DELAY = 30000

function getReconnectDelay(attempt) {
  const delay = Math.min(BASE_RECONNECT_DELAY * Math.pow(2, attempt), MAX_RECONNECT_DELAY)
  return delay + Math.random() * 1000
}

function notifyConnection(status, detail = '') {
  connectionListeners.forEach(cb => cb(status, detail))
}

export function connectWs(onUpdate, onConnectionChange) {
  wsCallbacks.add(onUpdate)
  if (onConnectionChange) connectionListeners.add(onConnectionChange)
  if (ws && ws.readyState === WebSocket.OPEN) return
  if (ws) ws.close()

  const token = getToken()
  if (!token) {
    console.warn('No token available for WebSocket connection')
    notifyConnection('sin_conexion', 'Sin token')
    return
  }
  notifyConnection('conectando')
  
  const wsUrl = `${getWsUrl()}?token=${encodeURIComponent(token)}`
  ws = new WebSocket(wsUrl)

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      wsCallbacks.forEach(cb => cb(data))
    } catch {}
  }

  ws.onclose = () => {
    ws = null
    reconnectAttempts++

    if (wsCallbacks.size > 0 && !reconnectTimer) {
      if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        console.error('Max WebSocket reconnect attempts reached')
        notifyConnection('sin_conexion', 'Sin conexión')
        wsCallbacks.forEach(cb => cb({ error: 'Max reconnection attempts reached' }))
        return
      }

      const delay = getReconnectDelay(reconnectAttempts)
      notifyConnection('reconectando', `Intento ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}`)
      console.log(`WebSocket reconnecting in ${Math.round(delay)}ms (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`)
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null
        connectWs()
      }, delay)
    }
  }

  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
    notifyConnection('reconectando', 'Error de conexión')
    ws.close()
  }
  
  ws.onopen = () => {
    reconnectAttempts = 0
    notifyConnection('en_vivo')
    console.log('WebSocket connected')
  }
}

export function disconnectWs(onUpdate, onConnectionChange) {
  wsCallbacks.delete(onUpdate)
  if (onConnectionChange) connectionListeners.delete(onConnectionChange)
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (wsCallbacks.size === 0 && ws) {
    ws.close()
    ws = null
  }
}

