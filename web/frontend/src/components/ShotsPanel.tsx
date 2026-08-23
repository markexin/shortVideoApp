import type { Shot } from '../types'

export function ShotsPanel({
  shots,
  onRegenerateShot,
  onGenerateVideo,
  busyShots,
}: {
  shots: Shot[]
  /** 只重新生成指定分镜，传入时为每个分镜头部显示「重新生成」按钮 */
  onRegenerateShot?: (shotId: number) => void
  /** 为指定分镜生成视频（复用参考图），传入时显示「生成视频」按钮 */
  onGenerateVideo?: (shotId: number) => void
  /** 按 shot_id 索引的忙碌态 */
  busyShots?: Record<number, boolean>
}) {
  if (shots.length === 0) {
    return (
      <div className="panel">
        <h3>分镜 ({shots.length})</h3>
        <div className="empty">暂无分镜信息</div>
      </div>
    )
  }
  return (
    <div className="panel">
      <h3>分镜 ({shots.length})</h3>
      <div className="shot-list">
        {shots.map((s) => (
          <ShotCard
            key={s.shot_id}
            shot={s}
            onRegenerateShot={onRegenerateShot}
            onGenerateVideo={onGenerateVideo}
            busyShot={busyShots?.[s.shot_id]}
          />
        ))}
      </div>
    </div>
  )
}

function ShotCard({
  shot,
  onRegenerateShot,
  onGenerateVideo,
  busyShot,
}: {
  shot: Shot
  onRegenerateShot?: (shotId: number) => void
  onGenerateVideo?: (shotId: number) => void
  busyShot?: boolean
}) {
  return (
    <div className="shot-card">
      <div className="shot-head">
        <span className="shot-num">镜 {shot.shot_id}</span>
        <span className={`badge badge-${shotStatusClass(shot.status)}`}>{shotStatus(shot.status)}</span>
        {onRegenerateShot && (
          <button
            className="btn btn-ghost btn-icon btn-small shot-regen"
            title={`只重新生成分镜 ${shot.shot_id}`}
            disabled={busyShot}
            onClick={() => onRegenerateShot(shot.shot_id)}
          >
            <span className="btn-glyph" aria-hidden>
              {busyShot ? '…' : '↻'}
            </span>
            <span>{busyShot ? '生成中' : '重生成'}</span>
          </button>
        )}
        {onGenerateVideo && (
          <button
            className="btn btn-ghost btn-icon btn-small shot-video"
            title={`根据参考图生成分镜 ${shot.shot_id} 的视频`}
            disabled={busyShot || !!shot.video_path}
            onClick={() => onGenerateVideo(shot.shot_id)}
          >
            <span className="btn-glyph" aria-hidden>
              {busyShot ? '…' : '▶'}
            </span>
            <span>{busyShot ? '生成中' : '生成视频'}</span>
          </button>
        )}
      </div>
      {shot.scene_description && <p className="shot-scene">{shot.scene_description}</p>}
      {shot.action && <p className="shot-action"><b>动作：</b>{shot.action}</p>}
      {shot.dialogue && <p className="shot-dialogue"><b>台词：</b>{shot.dialogue}</p>}
      <div className="shot-prompts">
        {shot.image_prompt && <PromptBox label="图生视频提示" text={shot.image_prompt} />}
        {shot.video_prompt && <PromptBox label="视频提示" text={shot.video_prompt} />}
      </div>
      <div className="shot-assets">
        {shot.image_path && <AssetChip label="参考图" value={shot.image_path} />}
        {shot.video_path && <AssetChip label="成片" value={shot.video_path} />}
      </div>
    </div>
  )
}

function PromptBox({ label, text }: { label: string; text: string }) {
  return (
    <div className="prompt-box small">
      <div className="prompt-label">{label}</div>
      <div className="prompt-text">{text}</div>
    </div>
  )
}

function AssetChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="asset-chip" title={value}>
      <span>{label}</span>
      <span className="asset-chip-path">{value}</span>
    </span>
  )
}

function shotStatus(status: string) {
  const map: Record<string, string> = {
    draft: '草稿',
    done: '完成',
    pending: '待生成',
  }
  return map[status] ?? status
}

function shotStatusClass(status: string) {
  if (status === 'done') return 'success'
  if (status === 'pending') return 'pending'
  return 'running'
}