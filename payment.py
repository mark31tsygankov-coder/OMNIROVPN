import logging, uuid
from dataclasses import dataclass
from typing import Optional
import aiohttp
from config import config
logger = logging.getLogger(__name__)

@dataclass
class PaymentResult:
    success: bool
    payment_id: Optional[str] = None
    payment_url: Optional[str] = None
    error: Optional[str] = None

class RollyPayProvider:
    async def create_payment(self, amount: float, description: str, user_id: int, order_id: int) -> PaymentResult:
        if not config.ROLLYPAY_API_KEY:
            return PaymentResult(False, error="Не задан ROLLYPAY_API_KEY")
        public_url = (config.PUBLIC_BASE_URL or "").strip().rstrip("/")
        if not public_url.startswith("https://") or "YOUR-HOST-DOMAIN" in public_url or "example.com" in public_url:
            return PaymentResult(False, error="Сначала укажите настоящий HTTPS-домен хостинга в PUBLIC_BASE_URL и настройте такой же Callback URL в RollyPay")
        if not config.ROLLYPAY_SIGNING_SECRET:
            return PaymentResult(False, error="Не задан ROLLYPAY_SIGNING_SECRET")
        payload = {
            "amount": f"{amount:.2f}", "payment_currency": "RUB",
            "order_id": f"omniro_{order_id}", "description": description,
            "customer_id": str(user_id),
        }
        if config.ROLLYPAY_TERMINAL_ID:
            payload["terminal_id"] = config.ROLLYPAY_TERMINAL_ID
        headers = {"X-API-Key": config.ROLLYPAY_API_KEY, "X-Nonce": str(uuid.uuid4()), "Content-Type": "application/json"}
        timeout = aiohttp.ClientTimeout(total=20)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"{config.ROLLYPAY_API_BASE}/api/v1/payments", json=payload, headers=headers) as r:
                    data = await r.json(content_type=None)
                    if r.status >= 300:
                        logger.error("RollyPay create payment failed: status=%s body=%s", r.status, str(data)[:500])
                        return PaymentResult(False, error=f"RollyPay HTTP {r.status}")
                    pay_url = data.get("pay_url")
                    if not pay_url:
                        return PaymentResult(False, error="RollyPay не вернул pay_url")
                    return PaymentResult(True, str(data.get("payment_id", "")), pay_url)
        except Exception as e:
            logger.exception("RollyPay request error")
            return PaymentResult(False, error=str(e))

class TestPaymentProvider:
    async def create_payment(self, amount, description, user_id, order_id):
        return PaymentResult(True, f"test_{order_id}", None)

class PaymentService:
    def __init__(self):
        self.provider = TestPaymentProvider() if config.TEST_MODE else RollyPayProvider()
    async def create_payment(self, amount, description, user_id, order_id):
        return await self.provider.create_payment(amount, description, user_id, order_id)
    async def confirm_test_payment(self, order_id):
        return bool(config.TEST_MODE)
payment_service = PaymentService()
