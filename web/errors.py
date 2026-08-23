"""Web 层统一错误响应。

业务层（pipeline / projects / workflows）没有自定义异常类型，
对外抛出的是标准 ValueError（参数/流程校验失败）与
RuntimeError（外部生成/合成失败）。这里把它们收敛为
结构化错误体，避免把堆栈或敏感信息泄露到前端。
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ProjectNotFoundError(Exception):
    """项目不存在时抛出，映射为 404。"""


class TaskNotFoundError(Exception):
    """任务不存在时抛出，映射为 404。"""


def _error_body(message: str) -> dict:
    return {"success": False, "error": message}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProjectNotFoundError)
    async def project_not_found(request: Request, exc: ProjectNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=_error_body(str(exc)))

    @app.exception_handler(TaskNotFoundError)
    async def task_not_found(request: Request, exc: TaskNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=_error_body(str(exc)))

    @app.exception_handler(ValueError)
    async def value_error(request: Request, exc: ValueError) -> JSONResponse:
        # 参数/状态机流程校验失败：属于客户端可修正的输入问题
        return JSONResponse(status_code=400, content=_error_body(str(exc)))

    @app.exception_handler(RuntimeError)
    async def runtime_error(request: Request, exc: RuntimeError) -> JSONResponse:
        # 外部依赖（LLM / ComfyUI / MiniMax / ffmpeg）失败
        return JSONResponse(status_code=502, content=_error_body(str(exc)))

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        # 未预期异常：仅返回通用消息，细节走服务端日志
        return JSONResponse(status_code=500, content=_error_body("内部服务错误"))