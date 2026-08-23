import type { TaskStatus } from '../types'

export function StatusBadge({ status }: { status: TaskStatus | string }) {
  return <span className={`badge badge-${status}`}>{label(status)}</span>
}

export function label(status: TaskStatus | string): string {
  switch (status) {
    case 'pending':
      return '等待中'
    case 'running':
      return '进行中'
    case 'completed':
      return '已完成'
    case 'failed':
      return '失败'
    case 'done':
      return '已完成'
    case 'active':
      return '进行中'
    case 'pending_stage':
      return '待执行'
    default:
      return status
  }
}

export function statusClass(status: TaskStatus | string): string {
  return status === 'running' || status === 'active'
    ? 'running'
    : status === 'completed' || status === 'done'
      ? 'success'
      : status === 'failed'
        ? 'failed'
        : 'pending'
}