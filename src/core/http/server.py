import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="Elemental Bot Control Panel")
templates = Jinja2Templates(directory="src/core/http/templates")


class ModelUpdate(BaseModel):
    model: str = Field(..., description="Название выбранной LLM модели")
    system_prompt: str = Field(..., description="Системный промпт")
    context_size: int = Field(..., ge=100, le=1000000, description="Размер контекста (Max Tokens)")
    init_data: str | None = Field(default=None, alias="initData", description="Telegram WebApp initData для верификации")


@app.get("/", response_class=JSONResponse)
async def health_check() -> dict[str, str]:
    """Эндпоинт для инспекторов от Hugging Face / Render."""
    return {"status": "ok", "message": "Полёт нормальный."}


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request) -> HTMLResponse:
    """Отображение панели управления Telegram Mini App."""
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        bot_ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            bot_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            bot_ip = "127.0.0.1"

    response: HTMLResponse = templates.TemplateResponse(
        request,
        "admin.html",
        {
            "current_model": settings.default_model,
            "bot_ip": bot_ip,
            "system_prompt": settings.system_prompt,
            "context_size": settings.max_tokens,
        },
    )
    return response


@app.post("/api/set-model", response_class=JSONResponse)
async def set_model(payload: ModelUpdate) -> JSONResponse:
    """Эндпоинт для смены языковой модели бота."""
    target_model = payload.model.strip()
    if not target_model:
        return JSONResponse(status_code=400, content={"error": "Название модели не может быть пустым."})

    is_openrouter = "/" in target_model
    if is_openrouter and not settings.openrouter_api_key:
        return JSONResponse(
            status_code=400,
            content={"error": f"Модель OpenRouter '{target_model}', но OPENROUTER_API_KEY не задан."},
        )
    if not is_openrouter and not settings.gemini_api_key:
        return JSONResponse(
            status_code=400,
            content={"error": f"Нативная модель Gemini '{target_model}', но GEMINI_API_KEY не задан."},
        )

    settings.default_model = target_model
    settings.system_prompt = payload.system_prompt
    settings.max_tokens = payload.context_size
    logger.info(
        "Настройки успешно обновлены через панель управления TMA: модель=%s, контекст=%d",
        target_model,
        payload.context_size,
    )
    return JSONResponse(
        content={
            "status": "success",
            "model": settings.default_model,
            "system_prompt": settings.system_prompt,
            "context_size": settings.max_tokens,
        }
    )


async def start_web_server() -> None:
    """Поднимает асинхронный веб-сервер на FastAPI и uvicorn.Server."""
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=settings.port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info("Веб-сервер FastAPI поднят в асинхронном контуре на порту %d.", settings.port)
    await server.serve()
