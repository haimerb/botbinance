export default function LabelWithTooltip({ label, tooltip }) {
  return (
    <span className="tooltip-wrap">
      {label}
      <span className="tooltip-icon" data-tooltip={tooltip}>?</span>
    </span>
  )
}
