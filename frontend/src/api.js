const BASE = '/api'

export function getToken() { return localStorage.getItem('token') }

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
    const err = await res.json()
    throw new Error(err.detail || `Error ${res.status}`)
  }
  return res.json()
}

export function setToken(t) { localStorage.setItem('token', t) }
export function clearToken() { localStorage.removeItem('token') }
export function isAuthenticated() { return !!getToken() }

export function register(email, password) {
  return request('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export function login(email, password) {
  return request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
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

export function getTrades(limit = 50) {
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

export function suggestConfig() {
  return request('/config/suggest')
}
