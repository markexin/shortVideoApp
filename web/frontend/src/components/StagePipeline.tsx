import type { StageView } from '../types'
import { describeStage, stageColor } from '../ui/helpers'

export function StagePipeline({
  stages,
  onClick,
}: {
  stages: StageView[]
  /** 点击某个已完成（或任意）节点的回调，传入该节点 index */
  onClick?: (index: number) => void
}) {
  return (
    <div className="stage-pipeline">
      {stages.map((s, i) => {
        const clickable = onClick && s.status !== 'pending'
        return (
          <div
            key={s.stage}
            className={`stage-node status-${stageColor(s.stage)} ${s.status}${clickable ? ' clickable' : ''}`}
            role={clickable ? 'button' : undefined}
            tabIndex={clickable ? 0 : undefined}
            onClick={clickable ? () => onClick(i) : undefined}
            onKeyDown={
              clickable
                ? (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onClick?.(i)
                    }
                  }
                : undefined
            }
          >
            <div className="stage-node-dot">
              <span className="stage-node-num">{s.index + 1}</span>
            </div>
            <div className="stage-node-body">
              <div className="stage-node-title">
                <span>{s.label}</span>
                <span className={`stage-node-status node-status-${s.status}`}>
                  {s.status === 'done' ? '已完成' : s.status === 'active' ? '进行中' : '待执行'}
                </span>
              </div>
              <div className="stage-node-desc muted">
                {describeStage(s).length > 0 ? describeStage(s).join(' · ') : '—'}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}