export default function NotificationBanner({ notification, onDismiss }) {
  if (!notification) return null
  const isEntry = notification.type === 'entry'
  const isExit = notification.type === 'exit' || notification.type === 'take_profit'
  const isLoss = notification.type === 'stop_loss'
  const cls = isEntry ? 'entry' : isExit ? 'exit' : 'loss'
  const symbol = notification.symbol?.replace('USDT', '') || '??'
  const action = isEntry ? 'Compra' : isLoss ? 'Stop Loss' : 'Venta'
  const dir = notification.side === 'BUY' ? '\u2191' : '\u2193'
  return (
    <div className={`notif notif-${cls}`} onClick={onDismiss}>
      <span className="notif-icon">{dir}</span>
      <span className="notif-body">
        <strong>{symbol}</strong> {action} @ ${Number(notification.price).toLocaleString('en-US', { minimumFractionDigits: 2 })}
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
