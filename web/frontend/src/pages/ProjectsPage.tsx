import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { createProject, listProjects } from '../api'
import type { ProjectSummary } from '../types'
import { Loading, Empty, ErrorBlock } from '../ui/Feedback'

export function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    try {
      const data = await listProjects()
      setProjects(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleCreate = async (values: CreateValues) => {
    setSubmitting(true)
    try {
      const created = await createProject(values)
      setShowCreate(false)
      await load()
      window.location.href = `/projects/${created.project_id}`
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <Loading text="正在加载项目列表…" />
  if (error && !projects) return <ErrorBlock message={error} />
  if (!projects) return <Loading text="正在加载项目列表…" />

  return (
    <section className="page">
      <div className="page-head">
        <h1>我的项目</h1>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + 新建项目
        </button>
      </div>

      {projects.length === 0 ? (
        <Empty text="暂无项目，右上角「新建项目」开始。" />
      ) : (
        <ProjectGrid projects={projects} />
      )}

      {showCreate && (
        <CreateDialog onClose={() => setShowCreate(false)} onSubmit={handleCreate} submitting={submitting} />
      )}
    </section>
  )
}

function ProjectGrid({ projects }: { projects: ProjectSummary[] }) {
  return (
    <div className="project-grid">
      {projects.map((p) => (
        <Link key={p.project_id} to={`/projects/${p.project_id}`} className="project-card">
          <div className="card-top">
            <span className="stage-pill small">{p.current_stage_label}</span>
          </div>
          <h3 className="card-title">{p.title}</h3>
          <ul className="card-meta">
            <li>{p.genre}</li>
            <li>{p.episode_count} 集</li>
            <li>{p.aspect_ratio}</li>
          </ul>
          <div className="card-progress">
            <div className="bar-fill" style={{ width: `${Math.round((p.stage_index / 7) * 100)}%` }} />
          </div>
          <div className="card-meta-row">
            <span>角色 {p.character_count}</span>
            <span>分镜 {p.shot_count}</span>
            <span>视频 {p.video_ready}/{p.shot_count}</span>
          </div>
        </Link>
      ))}
    </div>
  )
}

interface CreateValues {
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

function CreateDialog({
  onClose,
  onSubmit,
  submitting,
}: {
  onClose: () => void
  onSubmit: (v: CreateValues) => void
  submitting: boolean
}) {
  const [form, setForm] = useState<CreateValues>({
    title: '',
    premise: '',
    genre: '儿童教育短剧',
    platform: 'manual',
    aspect_ratio: '9:16',
    episode_count: 6,
    seconds_per_episode: 60,
    audience: '3-8岁儿童',
    pacing_style: '寓教于乐，单集有承转合',
  })

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>新建项目</h2>
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
            <span>剧名 *</span>
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              required
              autoFocus
              placeholder="例如：小刺猬的勇气之旅"
            />
          </label>
          <label>
            <span>创意前提</span>
            <textarea
              rows={3}
              value={form.premise}
              onChange={(e) => setForm({ ...form, premise: e.target.value })}
              placeholder="一句话描述故事核心"
            />
          </label>
          <div className="form-row">
            <label>
              <span>题材</span>
              <input value={form.genre} onChange={(e) => setForm({ ...form, genre: e.target.value })} />
            </label>
            <label>
              <span>画幅</span>
              <select value={form.aspect_ratio} onChange={(e) => setForm({ ...form, aspect_ratio: e.target.value })}>
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
                onChange={(e) => setForm({ ...form, episode_count: Number(e.target.value) })}
              />
            </label>
            <label>
              <span>单集秒数</span>
              <input
                type="number"
                min={15}
                max={600}
                value={form.seconds_per_episode}
                onChange={(e) => setForm({ ...form, seconds_per_episode: Number(e.target.value) })}
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              <span>目标受众</span>
              <input value={form.audience} onChange={(e) => setForm({ ...form, audience: e.target.value })} />
            </label>
            <label>
              <span>节奏风格</span>
              <input
                value={form.pacing_style}
                onChange={(e) => setForm({ ...form, pacing_style: e.target.value })}
              />
            </label>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting || !form.title}>
              {submitting ? '创建中…' : '创建'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}