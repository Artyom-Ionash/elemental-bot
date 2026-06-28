import logging

from aiohttp import web

from config import settings

logger = logging.getLogger(__name__)


async def health_check(request: web.Request) -> web.Response:
    """Эндпоинт для инспекторов от Hugging Face / Render."""
    return web.Response(text="Полёт нормальный.")


async def start_web_server() -> None:
    """Поднимает асинхронный веб-сервер на порту из конфигурации."""
    app = web.Application()
    app.router.add_get("/", health_check)

    runner = web.AppRunner(app)
    await runner.setup()

    port = settings.port
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Веб-сервер поднят в асинхронном контуре на порту %d.", port)
