import type { Character, VisualAsset } from '../types'

export function CharactersPanel({
  characters,
  assets,
  onChanged,
  onRegenerateCharacter,
  busyCharacters,
}: {
  characters: Character[]
  assets: VisualAsset[]
  /** 重新生成角色圣经，接收任务 id 以便页面轮询 */
  onChanged?: () => void
  /** 只重新生成指定角色，传入时为每个角色头部显示「重新生成」按钮 */
  onRegenerateCharacter?: (name: string) => void
  /** 按角色名索引的忙碌态（用于显示单角色的重新生成进度） */
  busyCharacters?: Record<string, boolean>
}) {
  const totalVariants = characters.reduce((n, c) => n + c.variants.length, 0)

  if (characters.length === 0) {
    return (
      <div className="panel">
        <div className="panel-head">
          <h3>角色圣经</h3>
          <span className="panel-sub">角色、场景、道具的视觉锚点集</span>
        </div>
        <div className="empty">暂无角色信息，请先生成角色圣经</div>
      </div>
    )
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h3>角色圣经</h3>
          <div className="panel-sub">
            {characters.length} 个角色 · {assets.length} 个场景/道具 · {totalVariants} 个造型变体
          </div>
        </div>
        <button
          className="btn btn-ghost btn-icon"
          title="重新生成角色圣经"
          onClick={onChanged}
        >
          <span className="btn-glyph" aria-hidden>
            ↻
          </span>
          <span>重新生成</span>
        </button>
      </div>

      <div className="character-grid">
        {characters.map((c, i) => (
          <div key={i} className="character-card">
            <div className="char-card-head">
              <h4>{c.name}</h4>
              {onRegenerateCharacter && (
                <button
                  className="btn btn-ghost btn-icon btn-small"
                  title={`只重新生成角色「${c.name}」`}
                  disabled={busyCharacters?.[c.name]}
                  onClick={() => onRegenerateCharacter(c.name)}
                >
                  <span className="btn-glyph" aria-hidden>
                    {busyCharacters?.[c.name] ? '…' : '↻'}
                  </span>
                  <span>
                    {busyCharacters?.[c.name] ? '生成中' : '重生成'}
                  </span>
                </button>
              )}
            </div>
            {c.description && <p className="char-desc">{c.description}</p>}
            <div className="char-prompts">
              {c.style_prompt && <PromptBox label="风格" text={c.style_prompt} />}
              {c.consistency_prompt && <PromptBox label="一致性" text={c.consistency_prompt} />}
              {c.negative_prompt && <PromptBox label="负面" text={c.negative_prompt} />}
            </div>
            {c.variants.length > 0 && (
              <div className="variant-list">
                {c.variants.map((v, j) => (
                  <div key={j} className="variant">
                    <span className="variant-name">
                      {v.name}
                      {v.story_stage ? ` · ${v.story_stage}` : ''}
                    </span>
                    {v.description && <span className="variant-desc">{v.description}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {assets.length > 0 && (
        <>
          <h3 className="section-title">场景与道具 ({assets.length})</h3>
          <div className="asset-grid">
            {assets.map((a, i) => (
              <div key={i} className="asset-card">
                <span className="tag">{a.category}</span>
                <h4>{a.name}</h4>
                {a.description && <p>{a.description}</p>}
                {a.image_prompt && <PromptBox label="图像提示" text={a.image_prompt} />}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function PromptBox({ label, text }: { label: string; text: string }) {
  return (
    <div className="prompt-box">
      <div className="prompt-label">{label}</div>
      <div className="prompt-text">{text}</div>
    </div>
  )
}