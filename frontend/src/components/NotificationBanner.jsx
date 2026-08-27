export default function NotificationBanner({ notification, onDismiss }) {
  if (!notification) return null
  const isError = notification.type === 'error'
  const isEntry = notification.type === 'entry'
  const isExit = notification.type === 'exit' || notification.type === 'take_profit'
  const isLoss = notification.type === 'stop_loss'
  const cls = isError ? 'error' : isEntry ? 'entry' : isExit ? 'exit' : 'loss'
  const symbol = notification.symbol?.replace('USDT', '') || '??'
  const action = isError ? 'Error' : isEntry ? 'Compra' : isLoss ? 'Stop Loss' : 'Venta'
  const dir = isError ? '\u2716' : notification.side === 'BUY' ? '\u2191' : '\u2193'
  return (
    <div className={`notif notif-${cls}`} onClick={onDismiss}>
      <span className="notif-icon">{dir}</span>
      <span className="notif-body">
        <strong>{symbol}</strong> {action}
        {!isError && <> @ ${Number(notification.price).toLocaleString('en-US', { minimumFractionDigits: 2 })}</>}
        {isError && notification.message && <> {notification.message}</>}
        {notification.pnl_pct != null && (
          <span className={notification.pnl_pct >= 0 ? 'green' : 'red'}>
            {' '}{notification.pnl_pct >= 0 ? '+' : ''}{notification.pnl_pct}%
          </span>
        )}
      </span>
      <span className="notif-close">\u00d7</span>
    </div>
  )
}
