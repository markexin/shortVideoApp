import { Routes, Route, Link, NavLink } from 'react-router-dom'
import { ProjectsPage } from './pages/ProjectsPage'
import { DetailPage } from './pages/DetailPage'
import { useEffect, useState } from 'react'
import { pingBackend } from './api'

function BackendStatus() {
  const [ok, setOk] = useState<boolean | null>(null)

  useEffect(() => {
    let live = false
    pingBackend().then((v) => {
      if (live) setOk(v)
    })
    live = true
    return () => {
      live = false
    }
  }, [])

  if (ok === null) return <span className="status-dot status-unknown" />
  if (ok) return <span className="status-dot status-ok" title="后端已连接" />
  return <span className="status-dot status-bad" title="后端未连接（请启动 web 服务）" />
}

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark">IV</span>
          <span className="brand-text">InstantVideo 短剧生产平台</span>
        </Link>
        <nav className="topnav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'nav-active' : '')}>
            项目列表
          </NavLink>
          <NavLink to="/stages" className={({ isActive }) => (isActive ? 'nav-active' : '')}>
            流水线说明
          </NavLink>
          <BackendStatus />
        </nav>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<DetailPage />} />
          <Route path="/stages" element={<StagesGuide />} />
          <Route path="*" element={<EmptyPage message="页面未找到" />} />
        </Routes>
      </main>
      <footer className="footer">InstantVideo Web Platform · Phase 3</footer>
    </div>
  )
}

function StagesGuide() {
  const stages = [
    { stage: 'home', label: '项目创建', note: '创建项目后进入脚本阶段' },
    { stage: 'script_confirm', label: '脚本生成', note: 'LLM 生成多剧本脚本' },
    { stage: 'script_confirmed', label: '脚本确认', note: '确认后进入角色生成' },
    { stage: 'characters_ready', label: '角色圣经', note: '生成角色设定与外观' },
    { stage: 'storyboard_ready', label: '分镜生成', note: '依据脚本+角色生成分镜' },
    { stage: 'image_prompts_exported', label: '图片准备', note: '导出/绑定分镜图片' },
    { stage: 'videos_ready', label: '视频生成', note: '图生视频，逐镜生成' },
    { stage: 'episode_ready', label: '整集合成', note: 'FFmpeg 合成最终视频' },
  ]
  return (
    <div className="stage-guide">
      <h2>流水线阶段说明</h2>
      <p className="muted">状态机按以下顺序推进，每阶段完成后可触发下一阶段（见项目详情页的「操作」区）。</p>
      <ol className="guide-list">
        {stages.map((s, i) => (
          <li key={s.stage}>
            <div className="guide-head">
              <span className="guide-num">{i + 1}</span>
              <span className="stage-pill">{s.label}</span>
            </div>
            <p className="guide-note">{s.note}</p>
          </li>
        ))}
      </ol>
    </div>
  )
}

function EmptyPage({ message }: { message: string }) {
  return (
    <div className="empty-state">
      <p>{message}</p>
    </div>
  )
}