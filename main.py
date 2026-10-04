import os
import asyncio
import logging
import time
from collections import defaultdict

import ccxt.async_support as ccxt
import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT").split(",") if s.strip()]
CAPITAL = float(os.getenv("CAPITAL_USDT", "350"))
MIN_SPREAD = float(os.getenv("MIN_NET_SPREAD_PCT", "0.5")) / 100
FEE = float(os.getenv("FEE_PER_SIDE_PCT", "0.1")) / 100
SAFETY = float(os.getenv("SAFETY_MARGIN_PCT", "0.1")) / 100
POLL_SECONDS = max(5, int(os.getenv("POLL_SECONDS", "10")))
COOLDOWN = max(60, int(os.getenv("ALERT_COOLDOWN_SECONDS", "900")))

last_alert = {}
last_error_notice = {}
telegram_session = None

async def telegram_send(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logging.warning("Telegram não configurado: defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        async with telegram_session.post(url, json={"chat_id": CHAT_ID, "text": message}) as resp:
            if resp.status != 200:
                logging.error("Telegram retornou HTTP %s", resp.status)
    except Exception:
        logging.exception("Falha ao enviar mensagem ao Telegram")

async def notify_error(exchange_name, error):
    now = time.time()
    if now - last_error_notice.get(exchange_name, 0) >= 1800:
        last_error_notice[exchange_name] = now
        await telegram_send(f"⚠️ {exchange_name}: consulta temporariamente indisponível. O monitor continuará tentando.")
    logging.warning("%s indisponível: %s", exchange_name, error)

async def fetch_book(exchange, symbol):
    return await exchange.fetch_order_book(symbol, limit=20)

def best_prices(book):
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    if not bids or not asks:
        return None
    return float(bids[0][0]), float(asks[0][0])

def executable_buy_cost(asks, budget):
    remaining = budget
    qty = 0.0
    cost = 0.0
    for price, amount in asks:
        price, amount = float(price), float(amount)
        take = min(amount, remaining / price)
        qty += take
        cost += take * price
        remaining -= take * price
        if remaining <= 1e-9:
            break
    return qty, cost

def executable_sell_value(bids, qty):
    remaining = qty
    value = 0.0
    for price, amount in bids:
        price, amount = float(price), float(amount)
        take = min(amount, remaining)
        value += take * price
        remaining -= take
        if remaining <= 1e-12:
            break
    return value, remaining

def compare_books(symbol, books):
    opportunities = []
    names = list(books)
    for buy_name in names:
        for sell_name in names:
            if buy_name == sell_name:
                continue
            buy_book = books[buy_name]
            sell_book = books[sell_name]
            qty, spend = executable_buy_cost(buy_book.get("asks", []), CAPITAL)
            if qty <= 0 or spend <= 0:
                continue
            proceeds, unfilled = executable_sell_value(sell_book.get("bids", []), qty)
            if unfilled > max(qty * 0.001, 1e-12):
                continue
            # Conservador: taxas em ambos os lados + margem de segurança.
            net = proceeds * (1 - FEE) - spend * (1 + FEE)
            net_pct = net / spend - SAFETY
            if net_pct >= MIN_SPREAD:
                opportunities.append((net_pct, buy_name, sell_name, spend, proceeds, net))
    return sorted(opportunities, reverse=True)

async def main():
    global telegram_session
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logging.warning("Variáveis do Telegram não configuradas.")
    timeout = aiohttp.ClientTimeout(total=15)
    telegram_session = aiohttp.ClientSession(timeout=timeout)
    exchanges = {
        "Bybit": ccxt.bybit({"enableRateLimit": True, "options": {"defaultType": "spot"}}),
        "OKX": ccxt.okx({"enableRateLimit": True, "options": {"defaultType": "spot"}}),
    }
    try:
        await telegram_send("🤖 Monitor Bybit + OKX iniciado. Apenas alertas; nenhuma ordem será enviada.")
        while True:
            for symbol in SYMBOLS:
                books = {}
                results = await asyncio.gather(
                    *(fetch_book(ex, symbol) for ex in exchanges.values()),
                    return_exceptions=True
                )
                for (name, ex), result in zip(exchanges.items(), results):
                    if isinstance(result, Exception):
                        await notify_error(name, result)
                    else:
                        books[name] = result
                if len(books) == 2:
                    for net_pct, buy_name, sell_name, spend, proceeds, net in compare_books(symbol, books):
                        key = (symbol, buy_name, sell_name)
                        now = time.time()
                        if now - last_alert.get(key, 0) >= COOLDOWN:
                            last_alert[key] = now
                            await telegram_send(
                                f"📊 Possível arbitragem {symbol}\n"
                                f"Comprar: {buy_name}\nVender: {sell_name}\n"
                                f"Valor estimado: {spend:.2f} USDT\n"
                                f"Venda estimada: {proceeds:.2f} USDT\n"
                                f"Resultado estimado após taxas: {net:.2f} USDT ({net_pct*100:.2f}%)\n"
                                "⚠️ Estimativa por livro de ofertas. Confira saldos, taxas reais, rede e preço antes de agir."
                            )
            await asyncio.sleep(POLL_SECONDS)
    finally:
        await asyncio.gather(*(ex.close() for ex in exchanges.values()), return_exceptions=True)
        await telegram_session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
