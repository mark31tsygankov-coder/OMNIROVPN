import hashlib, hmac, json, logging, time
from aiohttp import web
from config import config
from database import db
from handlers_subscription import activate_paid_order
logger = logging.getLogger(__name__)

def _valid_signature(raw: bytes, timestamp: str, signature: str) -> bool:
    secret = config.ROLLYPAY_SIGNING_SECRET
    if not secret or not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    # Reject stale/replayed callbacks outside a 10-minute window.
    if abs(int(time.time()) - ts) > 600:
        return False
    expected = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def create_app(bot):
    app = web.Application(client_max_size=64 * 1024)
    async def health(request):
        return web.json_response({"ok": True, "service": "omniro-rollypay-webhook"})
    async def webhook(request):
        raw = await request.read()
        if not _valid_signature(raw, request.headers.get("X-Timestamp", ""), request.headers.get("X-Signature", "")):
            return web.Response(status=403, text="Invalid signature")
        try:
            event = json.loads(raw.decode("utf-8"))
        except Exception:
            return web.Response(status=400, text="Invalid JSON")
        if event.get("status") == "paid" and event.get("event_type") == "payment.paid":
            ext_order = str(event.get("order_id", ""))
            if not ext_order.startswith("omniro_"):
                return web.Response(status=200, text="Ignored")
            try:
                order_id = int(ext_order.removeprefix("omniro_"))
            except ValueError:
                return web.Response(status=400, text="Invalid order")
            order = await db.get_order(order_id)
            if not order:
                logger.warning("RollyPay callback for unknown order %s", order_id)
                return web.Response(status=200, text="Unknown order")
            # Verify amount against stored order before fulfilment.
            try:
                if round(float(event.get("amount", 0)), 2) != round(float(order["amount"]), 2):
                    logger.error("Amount mismatch on order %s", order_id)
                    return web.Response(status=400, text="Amount mismatch")
            except (TypeError, ValueError):
                return web.Response(status=400, text="Invalid amount")
            if order["status"] != "paid":
                changed = await db.complete_order(order_id)
                if changed:
                    await activate_paid_order(order_id, bot)
        return web.Response(status=200, text="OK")
    app.router.add_get("/health", health)
    app.router.add_post(config.ROLLYPAY_CALLBACK_PATH, webhook)
    return app
