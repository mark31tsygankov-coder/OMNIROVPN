from aiogram import Router

from handlers_start import router as start_router
from handlers_subscription import router as subscription_router
from handlers_balance import router as balance_router
from handlers_support import router as support_router
from handlers_profile import router as profile_router
from handlers_documents import router as documents_router
from handlers_admin import router as admin_router


def setup_routers() -> Router:
    root = Router()
    root.include_router(start_router)
    root.include_router(subscription_router)
    root.include_router(balance_router)
    root.include_router(support_router)
    root.include_router(profile_router)
    root.include_router(documents_router)
    root.include_router(admin_router)
    return root
