export function TextPanel({ title, content, empty }: { title: string; content: string; empty: string }) {
  if (!content) {
    return (
      <div className="panel">
        <h3>{title}</h3>
        <div className="empty">{empty}</div>
      </div>
    )
  }
  return (
    <div className="panel text-panel">
      <h3>{title}</h3>
      <div className="text-content">{content}</div>
    </div>
  )
}