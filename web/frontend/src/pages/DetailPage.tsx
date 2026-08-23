import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getProject, trigger as triggerOp, updateProject } from '../api'
import { useTask } from '../hooks/useTask'
import { OP_TRIGGERS, type ProjectDetail, type TaskRecord, type StageView, type Character, type VisualAsset, type Shot } from '../types'
import { Loading, Empty, ErrorBlock } from '../ui/Feedback'
import { StagePipeline } from '../components/StagePipeline'
import { ScriptPanel } from '../components/ScriptPanel'
import { ShotsPanel } from '../components/ShotsPanel'
import { CharactersPanel } from '../components/CharactersPanel'
import { TriggerButton } from '../components/TriggerButton'
import { stageColor } from '../ui/helpers'

type Tab = 'overview' | 'script' | 'characters' | 'shots'

interface ProjectViewState {
  project: ProjectDetail | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export function DetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [view, setView] = useState<ProjectViewState>({
    project: null,
    loading: true,
    error: null,
    refresh: () => Promise.resolve(),
  })
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [triggerBusy, setTriggerBusy] = useState<Record<string, boolean>>({})
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [viewingStage, setViewingStage] = useState<number | null>(null)
  const [busyCharacters, setBusyCharacters] = useState<Record<string, boolean>>({})
  const [busyShots, setBusyShots] = useState<Record<number, boolean>>({})

  const load = useCallback(async () => {
    if (!projectId) return
    try {
      const data = await getProject(projectId)
      setView({ project: data, loading: false, error: null, refresh: load })
    } catch (e) {
      setView((v) => ({ ...v, loading: false, error: e instanceof Error ? e.message : String(e) }))
    }
  }, [projectId])

  useEffect(() => {
    load()
  }, [load])

  // 轮询当前正在执行的任务
  const { task, isPolling, error: taskError } = useTask(activeTaskId, { intervalMs: 1200 })

  // 后台任务完成后刷新项目，使 current_step / 阶段状态在界面上同步更新
  useEffect(() => {
    if (task && (task.status === 'completed' || task.status === 'failed')) {
      void load()
    }
  }, [task?.status, load])

  const activate = useCallback(
    async (op: string) => {
      if (!projectId) return
      setTriggerBusy((b) => ({ ...b, [op]: true }))
      try {
        const rec: TaskRecord = await triggerOp(projectId, op)
        setActiveTaskId(rec.task_id)
        await load()
      } catch (e) {
        window.alert(e instanceof Error ? e.message : String(e))
      } finally {
        setTriggerBusy((b) => ({ ...b, [op]: false }))
      }
    },
    [projectId, load],
  )

  const regenerateCharacter = useCallback(
    async (name: string) => {
      if (!projectId) return
      setBusyCharacters((b) => ({ ...b, [name]: true }))
      try {
        const rec: TaskRecord = await triggerOp(projectId, 'regenerate_character', {
          character_name: name,
        })
        setActiveTaskId(rec.task_id)
        await load()
      } catch (e) {
        window.alert(e instanceof Error ? e.message : String(e))
      } finally {
        setBusyCharacters((b) => ({ ...b, [name]: false }))
      }
    },
    [projectId, load],
  )

  const regenerateShot = useCallback(
    async (shotId: number) => {
      if (!projectId) return
      setBusyShots((b) => ({ ...b, [shotId]: true }))
      try {
        const rec: TaskRecord = await triggerOp(projectId, 'regenerate_shot', {
          shot_id: shotId,
        })
        setActiveTaskId(rec.task_id)
        await load()
      } catch (e) {
        window.alert(e instanceof Error ? e.message : String(e))
      } finally {
        setBusyShots((b) => ({ ...b, [shotId]: false }))
      }
    },
    [projectId, load],
  )

  const generateShotVideo = useCallback(
    async (shotId: number) => {
      if (!projectId) return
      setBusyShots((b) => ({ ...b, [shotId]: true }))
      try {
        const rec: TaskRecord = await triggerOp(projectId, 'generate_video', {
          shot_id: shotId,
        })
        setActiveTaskId(rec.task_id)
        await load()
      } catch (e) {
        window.alert(e instanceof Error ? e.message : String(e))
      } finally {
        setBusyShots((b) => ({ ...b, [shotId]: false }))
      }
    },
    [projectId, load],
  )

  const saveEdit = useCallback(
    async (values: EditValues) => {
      if (!projectId) return
      setSaving(true)
      try {
        await updateProject({ ...values, project_id: projectId })
        setEditing(false)
        await load()
      } catch (e) {
        window.alert(e instanceof Error ? e.message : String(e))
      } finally {
        setSaving(false)
      }
    },
    [projectId, load],
  )

  if (view.loading) return <Loading text="正在加载项目详情…" />
  if (view.error && !view.project) return <ErrorBlock message={view.error} />
  if (!view.project) return <Empty text="项目不存在" />

  const p = view.project

  return (
    <section className="page detail">
      <div className="page-head">
        <div>
          <h1>{p.title}</h1>
          <div className="subhead muted">
            <span className={`stage-pill small status-${stageColor(p.current_step)}`}>{p.current_stage_label}</span>
            <span>{p.genre} · {p.episode_count} 集 · {p.aspect_ratio}</span>
          </div>
        </div>
        <div className="page-head-actions">
          <button className="btn" onClick={load} disabled={isPolling}>
            {isPolling ? '同步中…' : '刷新'}
          </button>
          {p.can_edit && !editing && (
            <button className="btn btn-ghost" onClick={() => setEditing(true)}>
              ✎ 编辑项目
            </button>
          )}
        </div>
      </div>

      <StagePipeline
        stages={p.stage_overview}
        onClick={(i) => setViewingStage(i)}
      />

      {/* 当前任务状态条 */}
      {activeTaskId && task && (
        <div className={`task-banner task-${task.status}`}>
          <div>
            <strong>{OP_TRIGGERS[task.op]?.label ?? task.op}</strong>
            <span className="muted"> — {task.message || task.status}</span>
          </div>
          <div className="task-banner-right">
            <div className="mini-bar">
              <div className="mini-bar-fill" style={{ width: `${Math.round(task.progress * 100)}%` }} />
            </div>
            <span>{Math.round(task.progress * 100)}%</span>
          </div>
          {task.error && <pre className="task-error">{truncate(task.error)}</pre>}
          {taskError && <pre className="task-error">{truncate(taskError)}</pre>}
        </div>
      )}

      <div className="tabs">
        {(['overview', 'script', 'characters', 'shots'] as const).map((t) => (
          <button key={t} className={activeTab === t ? 'tab-active' : ''} onClick={() => setActiveTab(t)}>
            {tabLabel(t)}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {activeTab === 'overview' && (
          <OverviewCard
            project={p}
            activeTaskId={activeTaskId}
            triggerBusy={triggerBusy}
            activate={activate}
          />
        )}
        {activeTab === 'script' && (
          <ScriptPanel
            title="脚本"
            content={p.script}
            units={p.script_units}
            onRegenerate={p.can_edit ? () => activate('generate_script') : undefined}
            onEdit={p.can_edit ? () => setEditing(true) : undefined}
          />
        )}
        {activeTab === 'characters' && (
          <CharactersPanel
            characters={p.characters}
            assets={p.visual_assets}
            onChanged={p.current_step === 'characters_ready' ? () => activate('generate_characters') : undefined}
            onRegenerateCharacter={p.can_edit ? regenerateCharacter : undefined}
            busyCharacters={busyCharacters}
          />
        )}
        {activeTab === 'shots' && (
          <ShotsPanel
            shots={p.shots}
            onRegenerateShot={p.can_edit ? regenerateShot : undefined}
            onGenerateVideo={p.can_edit ? generateShotVideo : undefined}
            busyShots={busyShots}
          />
        )}
      </div>

      {editing && (
        <EditDialog
          project={p}
          onClose={() => setEditing(false)}
          onSubmit={saveEdit}
          saving={saving}
        />
      )}

      {viewingStage !== null && (
        <StageViewDialog
          stage={p.stage_overview[viewingStage]}
          onClose={() => setViewingStage(null)}
          detail={p}
        />
      )}
    </section>
  )
}

function OverviewCard({
  project,
  activeTaskId,
  triggerBusy,
  activate,
}: {
  project: ProjectDetail
  activeTaskId: string | null
  triggerBusy: Record<string, boolean>
  activate: (op: string) => void
}) {
  // 依据 current_step 决定可触发的流水线操作
  const opNames = ['generate_script', 'generate_characters', 'generate_storyboard', 'prepare_video', 'assemble_episode']

  return (
    <div className="cards-grid">
      <div className="panel overview-panel">
        <h3>项目信息</h3>
        <dl className="info-grid">
          <dt>创意前提</dt>
          <dd>{project.premise || '—'}</dd>
          <dt>节奏风格</dt>
          <dd>{project.pacing_style}</dd>
          <dt>目标受众</dt>
          <dd>{project.audience}</dd>
          <dt>平台</dt>
          <dd>{project.platform || '—'}</dd>
          <dt>创建时间</dt>
          <dd>{project.created_at}</dd>
          <dt>更新时间</dt>
          <dd>{project.updated_at}</dd>
        </dl>
      </div>

      <div className="panel actions-panel">
        <h3>流水线操作</h3>
        <p className="muted">点击后进入对应阶段，任务将后台执行（可实时看到进度）。</p>
        <div className="trigger-list">
          {opNames.map((op) => {
            const label = OP_TRIGGERS[op]?.label ?? op
            const enabled = !triggerBusy[op] && activeTaskId !== OP_TRIGGERS[op].op
            return (
              <TriggerButton
                key={op}
                op={op}
                label={label}
                disabled={!enabled}
                loading={triggerBusy[op]}
                active={activeTaskId === OP_TRIGGERS[op].op}
                onClick={() => activate(op)}
              />
            )
          })}
        </div>
      </div>
    </div>
  )
}

function tabLabel(t: string) {
  switch (t) {
    case 'overview':
      return '总览'
    case 'script':
      return '脚本'
    case 'characters':
      return '角色'
    case 'shots':
      return '分镜'
  }
  return t
}

function truncate(s: string, n = 100) {
  return s.length > n ? s.slice(0, n) + '…' : s
}

interface EditValues {
  title: string
  premise: string
  genre: string
  platform: string
  aspect_ratio: string
  episode_count: number
  seconds_per_episode: number
  audience: string
  pacing_style: string
}

function EditDialog({
  project,
  onClose,
  onSubmit,
  saving,
}: {
  project: ProjectDetail
  onClose: () => void
  onSubmit: (v: EditValues) => void
  saving: boolean
}) {
  const [form, setForm] = useState<EditValues>(() => ({
    title: project.title,
    premise: project.premise,
    genre: project.genre,
    platform: project.platform,
    aspect_ratio: project.aspect_ratio,
    episode_count: project.episode_count,
    seconds_per_episode: project.seconds_per_episode,
    audience: project.audience,
    pacing_style: project.pacing_style,
  }))

  const set = <K extends keyof EditValues>(key: K, value: EditValues[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const structuralFields = ['genre', 'aspect_ratio', 'episode_count', 'seconds_per_episode', 'audience', 'pacing_style']
  const changedStructural = structuralFields.some(
    (k) => (form as unknown as Record<string, unknown>)[k] !== (project as unknown as Record<string, unknown>)[k],
  )

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>编辑项目</h2>
          <button className="icon-btn" onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </div>
        <form
          className="modal-body"
          onSubmit={(e) => {
            e.preventDefault()
            onSubmit(form)
          }}
        >
          <label>
            <span>剧名</span>
            <input value={form.title} onChange={(e) => set('title', e.target.value)} autoFocus />
          </label>
          <label>
            <span>创意前提</span>
            <textarea
              rows={3}
              value={form.premise}
              onChange={(e) => set('premise', e.target.value)}
              placeholder="一句话描述故事核心"
            />
          </label>
          <div className="form-row">
            <label>
              <span>题材</span>
              <input value={form.genre} onChange={(e) => set('genre', e.target.value)} />
            </label>
            <label>
              <span>画幅</span>
              <select value={form.aspect_ratio} onChange={(e) => set('aspect_ratio', e.target.value)}>
                <option value="9:16">9:16 竖屏</option>
                <option value="16:9">16:9 横屏</option>
              </select>
            </label>
          </div>
          <div className="form-row">
            <label>
              <span>集数</span>
              <input
                type="number"
                min={1}
                max={50}
                value={form.episode_count}
                onChange={(e) => set('episode_count', Number(e.target.value))}
              />
            </label>
            <label>
              <span>单集秒数</span>
              <input
                type="number"
                min={15}
                max={600}
                value={form.seconds_per_episode}
                onChange={(e) => set('seconds_per_episode', Number(e.target.value))}
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              <span>目标受众</span>
              <input value={form.audience} onChange={(e) => set('audience', e.target.value)} />
            </label>
            <label>
              <span>节奏风格</span>
              <input value={form.pacing_style} onChange={(e) => set('pacing_style', e.target.value)} />
            </label>
          </div>
          {changedStructural && (
            <div className="form-notice">
              修改题材、画幅、集数、单集秒数、目标受众或节奏风格会<span>清空脚本、角色与分镜</span>，并回退到脚本阶段。
            </div>
          )}
          <div className="modal-actions">
            <button type="button" className="btn" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? '保存中…' : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function StageViewDialog({
  stage,
  onClose,
  detail,
}: {
  stage: StageView
  onClose: () => void
  detail: ProjectDetail
}) {
  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal wide" onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{stage.label} · 阶段产出</h2>
          <button className="icon-btn" onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </div>
        <div className="modal-body">
          <div className="stage-meta">
            <span className={`badge badge-success`}>已完成</span>
            {stage.metrics.script_complete !== undefined && (
              <span>脚本：{stage.metrics.script_complete ? '完整' : '不完整'}</span>
            )}
            {stage.metrics.episode_count !== undefined && (
              <span>集数：{String(stage.metrics.episode_count)}/{String(stage.metrics.expected_episode_count)}</span>
            )}
            {stage.metrics.character_count !== undefined && (
              <span>{String(stage.metrics.character_count)} 个角色</span>
            )}
            {stage.metrics.visual_asset_count !== undefined && (
              <span>{String(stage.metrics.visual_asset_count)} 项资产</span>
            )}
            {stage.metrics.shot_count !== undefined && (
              <span>{String(stage.metrics.shot_count)} 个分镜</span>
            )}
          </div>

          {renderStageContent(stage, detail)}
        </div>
      </div>
    </div>
  )
}

function renderStageContent(stage: StageView, detail: ProjectDetail) {
  // 脚本阶段：展示生成脚本
  if (stage.stage.startsWith('script')) {
    if (!detail.script) {
      return <div className="empty">暂无脚本内容</div>
    }
    // 脚本单元
    const units = detail.script_units
    if (units && units.length > 0) {
      return (
        <div className="units-list">
          {units.map((u) => (
            <div key={u.episode} className="unit-row">
              <div className="unit-title">第 {u.episode} 集 · {u.title}</div>
              {u.scene_count !== undefined && <div className="unit-count">{u.scene_count} 场戏</div>}
            </div>
          ))}
        </div>
      )
    }
    return <div className="script-block">{detail.script}</div>
  }

  // 角色阶段：展示角色
  if (stage.stage === 'characters_ready') {
    if (!detail.characters || detail.characters.length === 0) {
      return <div className="empty">暂无角色内容</div>
    }
    return <CharacterList characters={detail.characters} />
  }

  // 分镜阶段：展示分镜
  if (stage.stage === 'storyboard_ready') {
    if (!detail.shots || detail.shots.length === 0) {
      return <div className="empty">暂无分镜内容</div>
    }
    return <div className="shot-list">{detail.shots.map((s) => <ShotPreview key={s.shot_id} shot={s} />)}</div>
  }

  // 视觉资产阶段
  if (stage.stage === 'image_prompts_exported') {
    if (!detail.visual_assets || detail.visual_assets.length === 0) {
      return <div className="empty">暂无资产提示词</div>
    }
    return <AssetList assets={detail.visual_assets} />
  }

  return <div className="empty">该阶段暂无可展示内容</div>
}

function CharacterList({ characters }: { characters: Character[] }) {
  return (
    <div className="character-grid">
      {characters.map((c, i) => (
        <div key={i} className="character-card">
          <h4>{c.name}</h4>
          {c.description && <p className="char-desc">{c.description}</p>}
          {c.style_prompt && <div className="prompt-box"><div className="prompt-label">风格</div><div className="prompt-text">{c.style_prompt}</div></div>}
          {c.variants.length > 0 && (
            <div className="variant-list">
              {c.variants.map((v, j) => (
                <div key={j} className="variant">
                  <span className="variant-name">{v.name}{v.story_stage ? ` · ${v.story_stage}` : ''}</span>
                  {v.description && <span className="variant-desc">{v.description}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function AssetList({ assets }: { assets: VisualAsset[] }) {
  return (
    <div className="asset-grid">
      {assets.map((a, i) => (
        <div key={i} className="asset-card">
          <span className="tag">{a.category}</span>
          <h4>{a.name}</h4>
          {a.description && <p>{a.description}</p>}
          {a.image_prompt && <div className="prompt-box"><div className="prompt-label">图像提示</div><div className="prompt-text">{a.image_prompt}</div></div>}
        </div>
      ))}
    </div>
  )
}

function ShotPreview({ shot }: { shot: Shot }) {
  return (
    <div className="shot-card">
      <div className="shot-head">
        <span className="shot-num">镜 {shot.shot_id}</span>
        <span className="badge badge-success">完成</span>
      </div>
      {shot.scene_description && <p className="shot-scene">{shot.scene_description}</p>}
      {shot.action && <p className="shot-action"><b>动作：</b>{shot.action}</p>}
      {shot.dialogue && <p className="shot-dialogue"><b>台词：</b>{shot.dialogue}</p>}
    </div>
  )
}