import { useState, useEffect, useCallback, useRef } from 'react'
import * as api from '../api'
import LabelWithTooltip from './LabelWithTooltip'

const COMMON_SYMBOLS = [
  'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT',
  'DOGEUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT', 'MATICUSDT', 'UNIUSDT',
  'SHIBUSDT', 'LTCUSDT', 'ATOMUSDT', 'ETCUSDT', 'XLMUSDT', 'FILUSDT',
  'TRXUSDT', 'NEARUSDT', 'APTUSDT', 'ARBUSDT', 'OPUSDT', 'SUIUSDT',
  'PEPEUSDT', 'INJUSDT', 'TIAUSDT', 'SEIUSDT', 'RUNEUSDT', 'FETUSDT',
  'AAVEUSDT', 'ALGOUSDT', 'SANDUSDT', 'MANAUSDT', 'AXSUSDT', 'EGLDUSDT',
  'FTMUSDT', 'FLOWUSDT', 'ICPUSDT', 'KASUSDT', 'MKRUSDT', 'QNTUSDT',
  'THETAUSDT', 'VETUSDT', 'HBARUSDT', 'STXUSDT', 'RNDRUSDT',
]

const TOOLTIPS = {
  interval: 'Frecuencia de velas para analizar el mercado. Menor tiempo = más señales pero más ruido.',
  trade_quantity: 'Cantidad base del activo a comprar/vender por operación. Ajusta según el precio del símbolo.',
  stop_loss_pct: 'Porcentaje máximo de pérdida permitido antes de cerrar automáticamente la posición.',
  take_profit_pct: 'Porcentaje de ganancia objetivo para cerrar automáticamente la posición.',
  max_position_size: 'Cantidad máxima permitida para abrir una posición en una sola operación.',
  ma_fast_period: 'Período de la media móvil rápida. Valores menores reaccionan más rápido al precio.',
  ma_slow_period: 'Período de la media móvil lenta. Valores mayores filtran más ruido del mercado.',
  ml_confidence: 'Confianza mínima que debe tener el modelo ML para generar una señal. Mayor = menos señales pero más selectivas.',
  balance_allocation: 'Porcentaje del balance total que el bot puede usar para operar. El resto se mantiene como reserva.',
}

export default function AccountSettings({ user, onBack }) {
  const [profile, setProfile] = useState(null)
  const [config, setConfig] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const messageTimeoutRef = useRef(null)

  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [keyError, setKeyError] = useState('')
  const [keyLoading, setKeyLoading] = useState(false)
  const [showKeysForm, setShowKeysForm] = useState(false)
  const [newSymbol, setNewSymbol] = useState('')

  const showMessage = useCallback((msg) => {
    setMessage(msg)
    if (messageTimeoutRef.current) clearTimeout(messageTimeoutRef.current)
    messageTimeoutRef.current = setTimeout(() => setMessage(''), 3000)
  }, [])

  const fetchProfile = useCallback(async () => {
    try {
      const [p, c, s] = await Promise.all([api.getUserProfile(), api.getUserConfig(), api.getTradeStats()])
      setProfile(p)
      setConfig(c)
      setStats(s)
    } catch (e) {
      setMessage('Error al cargar perfil')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchProfile() }, [fetchProfile])

  const handleSaveConfig = async (e) => {
    e.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      const form = e.target
      const data = {
        interval: form.interval.value,
        trade_quantity: parseFloat(form.trade_quantity.value),
        stop_loss_pct: parseFloat(form.stop_loss_pct.value) / 100,
        take_profit_pct: parseFloat(form.take_profit_pct.value) / 100,
        max_position_size: parseFloat(form.max_position_size.value),
        ma_fast_period: parseInt(form.ma_fast_period.value),
        ma_slow_period: parseInt(form.ma_slow_period.value),
        ml_confidence_threshold: parseFloat(form.ml_confidence.value) / 100,
        balance_allocation_pct: parseFloat(form.balance_allocation.value),
        ai_stop_loss_enabled: form.ai_stop_loss ? form.ai_stop_loss.checked : false,
      }
      const updated = await api.updateUserConfig(data)
      setConfig(updated)
      showMessage('Configuración guardada')
    } catch (e) {
      setMessage(`Error: ${e.message}`)
    } finally {
      setSaving(false)
    }
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
      showMessage('API Keys guardadas')
    } catch (err) {
      setKeyError(err.message)
    } finally {
      setKeyLoading(false)
    }
  }

  const handleAddSymbol = async () => {
    const sym = newSymbol.toUpperCase().trim()
    if (!sym || !/^[A-Z0-9]{6,20}$/.test(sym)) {
      setMessage('Símbolo inválido (ej: ETHUSDT)')
      return
    }
    if (config.symbols.includes(sym)) {
      setMessage('El símbolo ya existe')
      return
    }
    const updated = await api.updateUserConfig({ symbols: [...config.symbols, sym] })
    setConfig(updated)
    setNewSymbol('')
    showMessage(`Símbolo ${sym} agregado`)
  }

  const handleRemoveSymbol = async (sym) => {
    if (config.symbols.length <= 1) {
      setMessage('Debe haber al menos un símbolo')
      return
    }
    const updated = await api.updateUserConfig({ symbols: config.symbols.filter(s => s !== sym) })
    setConfig(updated)
    showMessage(`Símbolo ${sym} eliminado`)
  }

  if (loading) return (
    <div className="loading-screen">
      <div className="loader" />
      <p>Cargando perfil...</p>
    </div>
  )

  return (
    <div className="page-account">
      <header>
        <div className="header-left">
          <span className="logo">
            <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
              <rect x="4" y="4" width="32" height="32" rx="8" stroke="currentColor" strokeWidth="2" fill="none"/>
              <path d="M13 20h14M20 13v14" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
            </svg>
          </span>
          <div>
            <h1>Mi Cuenta</h1>
            <span className="header-email">{profile?.email}</span>
          </div>
        </div>
        <div className="header-right">
          <button className="btn-ghost" onClick={onBack}>← Dashboard</button>
        </div>
      </header>

      {message && <div className="toast">{message}</div>}

      <div className="settings-grid">
        <div className="settings-section glass">
          <h3>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            Perfil
          </h3>
          <div className="settings-field">
            <span className="settings-label">Email</span>
            <span className="settings-value">{profile?.email}</span>
          </div>
          <div className="settings-field">
            <span className="settings-label">ID</span>
            <span className="settings-value mono">#{profile?.user_id}</span>
          </div>
          <div className="settings-field">
            <span className="settings-label">Miembro desde</span>
            <span className="settings-value">{profile?.created_at ? new Date(profile.created_at).toLocaleDateString('es', { year: 'numeric', month: 'long', day: 'numeric' }) : '--'}</span>
          </div>
          <div className="settings-field">
            <span className="settings-label">Símbolos activos</span>
            <span className="settings-value">{config?.symbols?.length || 0}</span>
          </div>
        </div>

        <div className="settings-section glass">
          <h3>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="1" x2="12" y2="23"/>
              <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
            </svg>
            Resumen de Operaciones
          </h3>
          <div className="settings-field">
            <span className="settings-label">Total trades</span>
            <span className="settings-value">{stats?.total_trades || 0}</span>
          </div>
          <div className="settings-field">
            <span className="settings-label">Win Rate</span>
            <span className={`settings-value ${(stats?.win_rate || 0) >= 50 ? 'green' : 'red'}`}>{stats?.win_rate || 0}%</span>
          </div>
          <div className="settings-field">
            <span className="settings-label">P&L Total</span>
            <span className={`settings-value ${(stats?.total_pnl_pct || 0) >= 0 ? 'green' : 'red'}`}>
              {stats?.total_pnl_pct != null ? `${stats.total_pnl_pct >= 0 ? '+' : ''}${stats.total_pnl_pct}%` : '0%'}
            </span>
          </div>
          <div className="settings-field">
            <span className="settings-label">Balance asignado</span>
            <span className="settings-value">{config?.balance_allocation_pct || 100}%</span>
          </div>
        </div>

        <div className="settings-section glass">
          <h3>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="11" width="18" height="11" rx="2" strokeLinecap="round"/>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
            API Keys
          </h3>
          {profile?.has_binance_keys ? (
            <p className="settings-note success">Keys configuradas</p>
          ) : (
            <p className="settings-note warn">No hay keys configuradas</p>
          )}
          <button className="btn-ghost settings-btn" onClick={() => setShowKeysForm(!showKeysForm)}>
            {showKeysForm ? 'Cancelar' : profile?.has_binance_keys ? 'Cambiar Keys' : 'Configurar Keys'}
          </button>
          {showKeysForm && (
            <form onSubmit={handleSaveKeys} className="settings-inline-form">
              <div className="field">
                <label>API Key</label>
                <input type="text" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="tu-api-key" required />
              </div>
              <div className="field">
                <label>Secret Key</label>
                <input type="password" value={apiSecret} onChange={e => setApiSecret(e.target.value)} placeholder="tu-secret-key" required />
              </div>
              {keyError && <div className="form-error">{keyError}</div>}
              <button type="submit" className="btn-primary" disabled={keyLoading}>
                {keyLoading ? 'Validando...' : 'Guardar y Validar'}
              </button>
            </form>
          )}
        </div>

        <div className="settings-section glass">
          <h3>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
            Configuración
          </h3>
          {config && (
            <>
              <div className="settings-field">
                <span className="settings-label">Intervalo</span>
                <span className="settings-value">{config.interval}</span>
              </div>
              <div className="settings-field">
                <span className="settings-label">Stop Loss</span>
                <span className="settings-value">{(config.stop_loss_pct * 100).toFixed(1)}%</span>
              </div>
              <div className="settings-field">
                <span className="settings-label">Take Profit</span>
                <span className="settings-value">{(config.take_profit_pct * 100).toFixed(1)}%</span>
              </div>
              <div className="settings-field">
                <span className="settings-label">MA Rápido/Lento</span>
                <span className="settings-value">{config.ma_fast_period}/{config.ma_slow_period}</span>
              </div>
            </>
          )}
        </div>

        <div className="settings-section full-width glass">
          <h3>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 20V10"/>
              <path d="M18 20V4"/>
              <path d="M6 20v-4"/>
            </svg>
            Configuración de Trading
          </h3>
          {config && (
            <form onSubmit={handleSaveConfig} className="settings-form">
              <div className="settings-form-grid">
                <div className="field">
                  <label><LabelWithTooltip label="Intervalo" tooltip={TOOLTIPS.interval} /></label>
                  <select name="interval" defaultValue={config.interval}>
                    <option value="15m">15 min</option>
                    <option value="30m">30 min</option>
                    <option value="1h">1 hora</option>
                    <option value="4h">4 horas</option>
                    <option value="1d">1 día</option>
                  </select>
                </div>
                <div className="field">
                  <label><LabelWithTooltip label="Cantidad por Trade" tooltip={TOOLTIPS.trade_quantity} /></label>
                  <input type="number" name="trade_quantity" step="0.0001" min="0.0001"
                    defaultValue={config.trade_quantity} required />
                </div>
                <div className="field">
                  <label><LabelWithTooltip label="Stop Loss (%)" tooltip={TOOLTIPS.stop_loss_pct} /></label>
                  <input type="number" name="stop_loss_pct" step="0.1" min="0.1" max="50"
                    defaultValue={(config.stop_loss_pct * 100).toFixed(1)} required />
                </div>
                <div className="field">
                  <label><LabelWithTooltip label="Take Profit (%)" tooltip={TOOLTIPS.take_profit_pct} /></label>
                  <input type="number" name="take_profit_pct" step="0.1" min="0.1" max="50"
                    defaultValue={(config.take_profit_pct * 100).toFixed(1)} required />
                </div>
                <div className="field">
                  <label><LabelWithTooltip label="Tamaño Máx. Posición" tooltip={TOOLTIPS.max_position_size} /></label>
                  <input type="number" name="max_position_size" step="0.001" min="0.001"
                    defaultValue={config.max_position_size} required />
                </div>
                <div className="field">
                  <label><LabelWithTooltip label="MA Rápido" tooltip={TOOLTIPS.ma_fast_period} /></label>
                  <input type="number" name="ma_fast_period" step="1" min="2" max="100"
                    defaultValue={config.ma_fast_period} required />
                </div>
                <div className="field">
                  <label><LabelWithTooltip label="MA Lento" tooltip={TOOLTIPS.ma_slow_period} /></label>
                  <input type="number" name="ma_slow_period" step="1" min="5" max="200"
                    defaultValue={config.ma_slow_period} required />
                </div>
                <div className="field">
                  <label><LabelWithTooltip label="Confianza ML (%)" tooltip={TOOLTIPS.ml_confidence} /></label>
                  <input type="number" name="ml_confidence" step="1" min="1" max="100"
                    defaultValue={(config.ml_confidence_threshold * 100).toFixed(0)} required />
                </div>
                <div className="field">
                  <label><LabelWithTooltip label="Balance Asignado (%)" tooltip={TOOLTIPS.balance_allocation} /></label>
                  <input type="number" name="balance_allocation" step="5" min="1" max="100"
                    defaultValue={config.balance_allocation_pct} required />
                </div>
                <div className="field">
                  <label>
                    <LabelWithTooltip label="Stop Loss Inteligente (IA)" tooltip="Usa la volatilidad del mercado para ajustar dinámicamente el stop-loss y take-profit. Recomendado para mercados volátiles." />
                  </label>
                  <label className="toggle-wrap">
                    <input type="checkbox" name="ai_stop_loss" defaultChecked={config.ai_stop_loss_enabled} />
                    <span className="toggle-track"><span className="toggle-thumb" /></span>
                  </label>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? 'Guardando...' : 'Guardar Configuración'}
                </button>
                <button type="button" className="btn-ghost" onClick={async () => {
                  try {
                    const res = await api.suggestConfig()
                    const sug = res.suggestions || {}
                    const form = document.querySelector('.settings-form')
                    if (form) {
                      if (sug.stop_loss_pct) form.stop_loss_pct.value = (sug.stop_loss_pct * 100).toFixed(1)
                      if (sug.take_profit_pct) form.take_profit_pct.value = (sug.take_profit_pct * 100).toFixed(1)
                      if (sug.trade_quantity) form.trade_quantity.value = sug.trade_quantity
                      if (sug.ma_fast_period) form.ma_fast_period.value = sug.ma_fast_period
                      if (sug.ma_slow_period) form.ma_slow_period.value = sug.ma_slow_period
                    }
                    showMessage('Parámetros sugeridos cargados. Revisa y guarda.')
                  } catch (e) {
                    setMessage(`Error: ${e.message}`)
                  }
                }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
                  </svg>
                  Optimizar con IA
                </button>
              </div>
            </form>
          )}
        </div>

        <div className="settings-section full-width glass">
          <h3>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 20h16"/>
              <path d="M4 20V4"/>
              <path d="M4 8h16"/>
              <path d="M4 12h16"/>
              <path d="M4 16h16"/>
            </svg>
            Símbolos
          </h3>
          <div className="symbols-list">
            {config?.symbols.map(sym => (
              <div key={sym} className="symbol-tag">
                <span>{sym}</span>
                <button className="symbol-remove" onClick={() => handleRemoveSymbol(sym)}
                  disabled={config.symbols.length <= 1}>×</button>
              </div>
            ))}
          </div>
          <div className="symbol-add">
            <input type="text" value={newSymbol} onChange={e => setNewSymbol(e.target.value.toUpperCase())}
              placeholder="ETHUSDT" className="mono" list="symbol-list" />
            <datalist id="symbol-list">
              {COMMON_SYMBOLS.filter(s => !config?.symbols?.includes(s)).map(s => (
                <option key={s} value={s} />
              ))}
            </datalist>
            <button className="btn-ghost" onClick={handleAddSymbol}>Agregar</button>
          </div>
        </div>
      </div>
    </div>
  )
}
