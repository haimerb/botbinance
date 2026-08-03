import { useState, useEffect, useCallback, useRef, memo } from 'react'
import * as api from '../api'
import SymbolCard from './SymbolCard'
import MetricCard from './MetricCard'
import PriceMiniChart from './PriceMiniChart'
import NotificationBanner from './NotificationBanner'
import TradeTable from './TradeTable'

function Dashboard({ user, onLogout, onAccount }) {
  const [state, setState] = useState(null)
  const [trades, setTrades] = useState([])
  const [stats, setStats] = useState(null)
  const [priceHistory, setPriceHistory] = useState({})
  const [tradeLimit, setTradeLimit] = useState(5)
  const [activeSymbol, setActiveSymbol] = useState(null)
  const [showKeysForm, setShowKeysForm] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [keyError, setKeyError] = useState('')
  const [keyLoading, setKeyLoading] = useState(false)
  const [notification, setNotification] = useState(null)
  const lastTradeIdRef = useRef(0)
  const priceHistoryRef = useRef({})
  const notifTimeoutRef = useRef(null)

  const handleWsUpdate = useCallback((data) => {
    setState(prev => {
      if (!prev) return data
      return { ...prev, ...data }
    })
    if (data?.current_prices) {
      const hist = priceHistoryRef.current
      Object.entries(data.current_prices).forEach(([sym, price]) => {
        if (price) {
          const arr = hist[sym] || []
          if (arr.length === 0 || arr[arr.length - 1] !== price) {
            hist[sym] = [...arr.slice(-29), price]
          }
        }
      })
      setPriceHistory({ ...hist })
    }
  }, [])

  const fetchTradesAndStats = useCallback(async () => {
    try {
      const [s, t, st] = await Promise.all([api.getStatus(), api.getTrades(tradeLimit), api.getTradeStats()])
      if (!state) setState(s)
      setTrades(t.trades || [])
      setStats(st)

      const serverLastId = s?.last_trade_id || 0
      if (serverLastId > lastTradeIdRef.current) {
        try {
          const recent = await api.getRecentTrades(lastTradeIdRef.current)
          const newTrades = recent.trades || []
          if (newTrades.length > 0) {
            const latest = newTrades[newTrades.length - 1]
            if (latest.type === 'entry' || latest.type === 'exit' || latest.type === 'stop_loss' || latest.type === 'take_profit') {
              setNotification(latest)
              if (notifTimeoutRef.current) clearTimeout(notifTimeoutRef.current)
              notifTimeoutRef.current = setTimeout(() => setNotification(null), 5000)
            }
          }
        } catch {}
        lastTradeIdRef.current = serverLastId
      }

      if (s?.symbols?.length && !activeSymbol) {
        setActiveSymbol(s.symbols[0])
      }
    } catch {}
  }, [tradeLimit, activeSymbol, state])

  useEffect(() => {
    api.connectWs(handleWsUpdate)
    fetchTradesAndStats()
    const interval = setInterval(fetchTradesAndStats, 5000)
    return () => { api.disconnectWs(handleWsUpdate); clearInterval(interval) }
  }, [handleWsUpdate, fetchTradesAndStats])

  useEffect(() => {
    if (state?.symbols?.length && activeSymbol && !state.symbols.includes(activeSymbol)) {
      setActiveSymbol(state.symbols[0])
    }
  }, [state?.symbols])

  const handleStart = async () => {
    try { await api.startBot(); fetchTradesAndStats() } catch (e) { setNotification({ type: 'error', message: e.message }); notifTimeoutRef.current = setTimeout(() => setNotification(null), 5000) }
  }
  const handleStop = async () => {
    try { await api.stopBot(); fetchTradesAndStats() } catch (e) { setNotification({ type: 'error', message: e.message }); notifTimeoutRef.current = setTimeout(() => setNotification(null), 5000) }
  }

  const handleSaveKeys = async (e) => {
    e.preventDefault()
    setKeyError('')
    setKeyLoading(true)
    try {
      await api.saveBinanceKeys(apiKey, apiSecret)
      setShowKeysForm(false)
      setApiKey('')
      setApiSecret('')
    } catch (err) {
      setKeyError(err.message)
    } finally {
      setKeyLoading(false)
    }
  }

  const isRunning = state?.status === 'running'
  const isMock = state?.mock_mode
  const symbols = state?.symbols || []
  const currentPrices = state?.current_prices || {}
  const positions = state?.positions || {}
  const signals = state?.signals || {}

  const primaryPrice = currentPrices[activeSymbol] || 0
  const primaryHist = priceHistory[activeSymbol] || []
  const priceChange = primaryHist.length > 1
    ? ((primaryPrice - primaryHist[0]) / primaryHist[0] * 100).toFixed(2)
    : '0.00'
  const primarySig = signals[activeSymbol] || {}

  return (
    <>
      <NotificationBanner notification={notification} onDismiss={() => setNotification(null)} />
      <header>
        <div className="header-left">
          <span className="logo">
            <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
              <rect x="4" y="4" width="32" height="32" rx="8" stroke="currentColor" strokeWidth="2" fill="none"/>
              <path d="M13 20h14M20 13v14" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
              <circle cx="20" cy="20" r="4" fill="currentColor" opacity="0.15"/>
            </svg>
          </span>
          <div>
            <h1>Binance Bot</h1>
            <span className="header-email">{user?.email}</span>
          </div>
        </div>
        <div className="header-right">
          {isMock && <span className="badge mock">SIMULACIÓN</span>}
          <div className={`badge ${isRunning ? 'running' : 'stopped'}`}>
            <span className="badge-dot" />
            {isRunning ? 'En Vivo' : 'Detenido'}
          </div>
          <button className="btn-ghost" onClick={onAccount}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            Mi Cuenta
          </button>
          <button className="btn-ghost" onClick={onLogout}>Salir</button>
        </div>
      </header>

      <div className="symbols-bar">
        {symbols.map(sym => (
          <SymbolCard
            key={sym}
            symbol={sym}
            price={currentPrices[sym]}
            signal={signals[sym]}
            position={positions[sym]}
            active={sym === activeSymbol}
            onClick={() => setActiveSymbol(sym)}
          />
        ))}
      </div>

      <div className="price-banner glass">
        <div className="price-main">
          <span className="price-symbol">{activeSymbol?.replace('USDT', '/USDT') || '---'}</span>
          <span className={`price-value ${priceChange >= 0 ? 'up' : 'down'}`}>
            ${primaryPrice.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </span>
        </div>
        <div className="price-change">
          <span className={priceChange >= 0 ? 'up' : 'down'}>
            {priceChange >= 0 ? '\u25b2' : '\u25bc'} {Math.abs(priceChange)}%
          </span>
          <PriceMiniChart history={primaryHist} />
        </div>
      </div>

      <div className="controls">
        <button className="btn-primary btn-icon" onClick={handleStart} disabled={isRunning}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          Iniciar
        </button>
        <button className="btn-danger btn-icon" onClick={handleStop} disabled={!isRunning}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
          Detener
        </button>
        <button className="btn-ghost" onClick={() => setShowKeysForm(!showKeysForm)}>
          {showKeysForm ? 'Cancelar' : user?.has_binance_keys ? 'API Keys' : 'Configurar API'}
        </button>
      </div>

      {showKeysForm && (
        <div className="keys-form glass">
          <h3>API Keys de Binance</h3>
          <form onSubmit={handleSaveKeys}>
            <div className="field">
              <label>API Key</label>
              <input type="text" value={apiKey} onChange={e => setApiKey(e.target.value)}
                placeholder="tu-api-key" required />
            </div>
            <div className="field">
              <label>Secret Key</label>
              <input type="password" value={apiSecret} onChange={e => setApiSecret(e.target.value)}
                placeholder="tu-secret-key" required />
            </div>
            {keyError && <div className="form-error">{keyError}</div>}
            <button type="submit" className="btn-primary" disabled={keyLoading}>
              {keyLoading ? 'Validando...' : 'Guardar y Validar'}
            </button>
          </form>
        </div>
      )}

      <div className="metrics-grid">
        <MetricCard title="Precio" value={`$${primaryPrice.toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
          sub={state?.last_update ? new Date(state.last_update).toLocaleTimeString() : '--'} trend="info" />
        <MetricCard title="Señal MA" value={primarySig.ma || 'HOLD'}
          sub="Media Móvil" trend={primarySig.ma === 'BUY' ? 'up' : primarySig.ma === 'SELL' ? 'down' : ''} />
        <MetricCard title="Señal ML" value={primarySig.ml || 'HOLD'}
          sub="Stacking Ensemble" trend={primarySig.ml === 'BUY' ? 'up' : primarySig.ml === 'SELL' ? 'down' : ''} />
        <MetricCard title="Balance Total" value={`$${(state?.total_balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
          sub={`Asignado: $${(state?.balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
          trend={state?.pnl >= 0 ? 'up' : 'down'} />
        <MetricCard title="Posición" value={positions[activeSymbol] ? 'Activa' : '—'}
          sub={positions[activeSymbol] ? `Entry: $${positions[activeSymbol].entry?.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : 'Esperando'}
          trend={positions[activeSymbol] ? 'up' : ''} />
        <MetricCard title="Modelo ML" value={`${state?.model_accuracy || 0}%`}
          sub="Precisión" trend="info" />
      </div>

      {stats && (
        <div className="stats-row">
          <div className="stat-item">
            <span className="stat-label">Operaciones</span>
            <span className="stat-value">{stats.total_trades}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Ganadas</span>
            <span className="stat-value green">{stats.wins}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Perdidas</span>
            <span className="stat-value red">{stats.losses}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Win Rate</span>
            <span className={`stat-value ${stats.win_rate >= 50 ? 'green' : 'red'}`}>{stats.win_rate}%</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">P&L Total</span>
            <span className={`stat-value ${stats.total_pnl_pct >= 0 ? 'green' : 'red'}`}>
              {stats.total_pnl_pct >= 0 ? '+' : ''}{stats.total_pnl_pct}%
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Promedio</span>
            <span className={`stat-value ${stats.avg_pnl_pct >= 0 ? 'green' : 'red'}`}>
              {stats.avg_pnl_pct >= 0 ? '+' : ''}{stats.avg_pnl_pct}%
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Mejor</span>
            <span className="stat-value green">+{stats.best_trade}%</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Peor</span>
            <span className="stat-value red">{stats.worst_trade}%</span>
          </div>
        </div>
      )}

      <div className="section glass">
        <div className="section-header">
          <h2>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
            Historial de Operaciones
          </h2>
          <div className="section-header-right">
            <select className="limit-select" value={tradeLimit} onChange={e => setTradeLimit(Number(e.target.value))}>
              <option value="5">5</option>
              <option value="10">10</option>
              <option value="25">25</option>
              <option value="50">50</option>
              <option value="100">100</option>
              <option value="500">Todo</option>
            </select>
            <span className="count">{trades.length} trades</span>
          </div>
        </div>
        <TradeTable trades={trades} tradeLimit={tradeLimit} onLimitChange={setTradeLimit} />
      </div>
    </>
  )
}

export default memo(Dashboard)
