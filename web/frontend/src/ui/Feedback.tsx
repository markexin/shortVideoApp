export function Spinner({ size = 16 }: { size?: number }) {
  return <span className="spinner" style={{ width: size, height: size }} aria-label="加载中" />
}

export function Loading({ text = '加载中...' }: { text?: string }) {
  return (
    <div className="block-loading">
      <Spinner />
      <span>{text}</span>
    </div>
  )
}

export function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>
}

export function ErrorBlock({ message }: { message: string }) {
  return <div className="error-block">{message}</div>
}