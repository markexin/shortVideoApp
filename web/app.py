"""InstantVideo Web 管理平台后端入口。

以 ASGI 应用工厂方式组织，便于测试注入与后续扩展。
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中（直接以 uvicorn web.app:app 启动时）
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.api import ops
from web.api import projects as projects_module
from web.errors import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="InstantVideo Web Platform", version="0.1.0")

    # 开发阶段允许前端 dev server（默认 Vite 5173）跨域访问 API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(projects_module.router, prefix="/api")
    app.include_router(ops.router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict:
        return {"success": True, "data": {"status": "ok", "service": "instantvideo-web"}}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)