import asyncio
import logging
import pathlib

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = pathlib.Path(__file__).resolve().parent


async def miniapp_index(request: web.Request):
    # отдаём твой index.html как мини-апп
    return web.FileResponse(path=BASE_DIR / "index.html")


async def on_startup(bot: Bot):
    # ставим webhook на Railway домен
    await bot.set_webhook(f"{settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}")
    logger.info("Webhook set: %s%s", settings.WEBHOOK_HOST, settings.WEBHOOK_PATH)


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    logger.info("Webhook deleted")


def main():
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # middlewares можно оставить — они не должны ломать старт
    from middlewares.logging_middleware import LoggingMiddleware
    dp.update.middleware(LoggingMiddleware())

    # ВАЖНО: BanMiddleware трогает базу, а базы на Railway пока нет — отключаем
    # from middlewares.ban_middleware import BanMiddleware
    # dp.update.middleware(BanMiddleware())

    # роутеры
    from handlers.users.start import router as start_router
    from handlers.users.profile import router as profile_router
    from handlers.ads.create import router as create_router
    from handlers.ads.search import router as search_router
    from handlers.ads.view import router as view_router
    from handlers.chats.comm import router as chat_router
    from handlers.favorites.fav import router as fav_router
    from handlers.admin.moderation import router as moderation_router
    from handlers.admin.panel import router as panel_router

    dp.include_router(start_router)
    dp.include_router(profile_router)
    dp.include_router(create_router)
    dp.include_router(search_router)
    dp.include_router(view_router)
    dp.include_router(chat_router)
    dp.include_router(fav_router)
    dp.include_router(moderation_router)
    dp.include_router(panel_router)

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()

    # mini app
    app.router.add_get("/", miniapp_index)

    # webhook handler
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=settings.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Railway почти всегда даёт порт в переменной PORT.
    # Если PORT нет — используем WEB_SERVER_PORT из конфига.
    port = int(getattr(settings, "WEB_SERVER_PORT", 8080))
    try:
        import os
        if os.getenv("PORT"):
            port = int(os.getenv("PORT"))
    except Exception:
        pass

    web.run_app(app, host=settings.WEB_SERVER_HOST, port=port)


if __name__ == "__main__":
    main()

    main()
