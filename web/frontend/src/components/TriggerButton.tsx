import { Spinner } from '../ui/Feedback'
import { stageColor } from '../ui/helpers'

export function TriggerButton({
  op,
  label,
  disabled,
  loading,
  active,
  onClick,
}: {
  op: string
  label: string
  disabled: boolean
  loading: boolean
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      className={`trigger-btn ${active ? 'active' : ''} ${disabled ? 'disabled' : ''}`}
      disabled={disabled || loading}
      onClick={onClick}
    >
      <span className={`trigger-dot status-${stageColor(op)}`} />
      <span className="trigger-label">{label}</span>
      {loading || active ? <Spinner size={16} /> : null}
    </button>
  )
}