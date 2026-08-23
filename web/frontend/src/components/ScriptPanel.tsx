import type { ScriptUnit } from '../types'

export function ScriptPanel({
  title,
  content,
  units,
  onRegenerate,
  onEdit,
}: {
  title: string
  content: string
  units: ScriptUnit[]
  /** 重新生成脚本，接收任务 id 以便页面轮询 */
  onRegenerate?: () => void
  /** 二次编辑项目设定（题材/集数等），会重置流水线 */
  onEdit?: () => void
}) {
  const unitCount = (units || []).length

  if (!content) {
    return (
      <div className="panel">
        <div className="panel-head">
          <h3>{title}</h3>
          <span className="panel-sub">{unitCount ? `${unitCount} 集` : '—'}</span>
        </div>
        <div className="empty">暂无脚本内容，请先生成脚本</div>
      </div>
    )
  }

  return (
    <div className="panel text-panel">
      <div className="panel-head">
        <div>
          <h3>{title}</h3>
          <div className="panel-sub">
            {unitCount ? `${unitCount} 集 · 分集大纲` : '单档文本'}
          </div>
        </div>
        <div className="panel-head-actions">
          {onEdit && (
            <button
              className="btn btn-ghost btn-icon"
              title="编辑项目设定（题材/集数等，会重置流水线）"
              onClick={onEdit}
            >
              <span className="btn-glyph" aria-hidden>
                ✎
              </span>
              <span>编辑</span>
            </button>
          )}
          {onRegenerate && (
            <button
              className="btn btn-ghost btn-icon"
              title="基于当前设定重新生成脚本"
              onClick={onRegenerate}
            >
              <span className="btn-glyph" aria-hidden>
                ↻
              </span>
              <span>重新生成</span>
            </button>
          )}
        </div>
      </div>

      <div className="text-content">{content}</div>
    </div>
  )
}