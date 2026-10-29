import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database import db
from handlers_setup import setup_routers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting bot...")
    logger.info("TEST_MODE=%s | ADMIN_ID=%s", config.TEST_MODE, config.ADMIN_ID)

    await db.init()
    logger.info("Database initialized")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(setup_routers())

    # Start callback listener alongside Telegram polling. Public HTTPS URL must be configured in RollyPay.
    runner = None
    if not config.TEST_MODE:
        from aiohttp import web
        from rollypay_webhook import create_app
        if not config.ROLLYPAY_API_KEY or not config.ROLLYPAY_SIGNING_SECRET:
            logger.warning("RollyPay credentials missing: payments will fail until ROLLYPAY_API_KEY and ROLLYPAY_SIGNING_SECRET are set")
        runner = web.AppRunner(create_app(bot))
        await runner.setup()
        site = web.TCPSite(runner, config.WEBHOOK_HOST, config.PORT)
        await site.start()
        logger.info("RollyPay webhook listening on %s:%s%s", config.WEBHOOK_HOST, config.PORT, config.ROLLYPAY_CALLBACK_PATH)
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot is running. Press Ctrl+C to stop.")
    try:
        await dp.start_polling(bot)
    finally:
        if runner:
            await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
