import os, time, asyncio, logging
import aiohttp
import ccxt.async_support as ccxt

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CAPITAL_USDT = float(os.getenv("CAPITAL_USDT", "350"))
MIN_NET_SPREAD = float(os.getenv("MIN_NET_SPREAD", "0.005"))
FEE_BUY = float(os.getenv("FEE_BUY", "0.001"))
FEE_SELL = float(os.getenv("FEE_SELL", "0.001"))
SAFETY_MARGIN = float(os.getenv("SAFETY_MARGIN", "0.001"))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "8"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "900"))
SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT").split(",") if s.strip()]
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

async def telegram(session, message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        async with session.post(url, data={"chat_id": CHAT_ID, "text": message}) as r:
            if r.status != 200:
                logging.warning("Telegram returned HTTP %s", r.status)
    except Exception:
        logging.exception("Falha ao enviar mensagem ao Telegram")

def executable_vwap(levels, quote_budget):
    remaining, base, quote = quote_budget, 0.0, 0.0
    for price, amount in levels:
        if price <= 0 or amount <= 0:
            continue
        take = min(amount, remaining / price)
        base += take
        quote += take * price
        remaining -= take * price
        if remaining <= 1e-8:
            break
    if remaining > max(0.01, quote_budget * 0.001):
        return None
    return base, quote

async def safe_load_markets(exchange, name):
    try:
        await exchange.load_markets()
        logging.info("%s: mercados carregados", name)
        return True
    except Exception as e:
        logging.error("%s: não foi possível carregar mercados (%s): %s", name, type(e).__name__, e)
        return False

async def main():
    binance = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    bybit = ccxt.bybit({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    exchanges = {"Binance": binance, "Bybit": bybit}
    last_alert = {}
    last_error_log = {}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        # Sem mensagem de inicialização no Telegram: evita notificações repetidas a cada reinício.
        try:
            while True:
                ready = {}
                for name, exchange in exchanges.items():
                    ready[name] = await safe_load_markets(exchange, name) if not exchange.markets else True

                if not all(ready.values()):
                    logging.warning("Aguardando acesso às duas corretoras; nenhuma oportunidade será calculada.")
                    await asyncio.sleep(max(POLL_SECONDS, 30))
                    continue

                for symbol in SYMBOLS:
                    if symbol not in binance.markets or symbol not in bybit.markets:
                        logging.info("Par %s indisponível em uma das corretoras", symbol)
                        continue
                    try:
                        results = await asyncio.gather(
                            binance.fetch_order_book(symbol, limit=20),
                            bybit.fetch_order_book(symbol, limit=20),
                            return_exceptions=True
                        )
                        ob_a, ob_b = results
                        if isinstance(ob_a, Exception) or isinstance(ob_b, Exception):
                            for name, result in (("Binance", ob_a), ("Bybit", ob_b)):
                                if isinstance(result, Exception):
                                    msg = f"{name} {type(result).__name__}: {result}"
                                    # Evita inundar os logs com o mesmo erro a cada ciclo.
                                    now = time.time()
                                    if now - last_error_log.get(name, 0) > 300:
                                        logging.error(msg)
                                        last_error_log[name] = now
                            continue

                        candidates = [
                            ("Binance", "Bybit", ob_a["asks"], ob_b["bids"]),
                            ("Bybit", "Binance", ob_b["asks"], ob_a["bids"])
                        ]
                        for buy_name, sell_name, asks, bids in candidates:
                            buy = executable_vwap(asks, CAPITAL_USDT)
                            if not buy:
                                continue
                            qty, spend = buy
                            remaining, proceeds = qty, 0.0
                            for price, amount in bids:
                                take = min(amount, remaining)
                                proceeds += take * price
                                remaining -= take
                                if remaining <= 1e-12:
                                    break
                            if remaining > max(1e-10, qty * 0.001):
                                continue
                            net_proceeds = proceeds * (1 - FEE_SELL)
                            net_cost = spend * (1 + FEE_BUY)
                            net_spread = (net_proceeds - net_cost) / net_cost - SAFETY_MARGIN
                            key = (symbol, buy_name, sell_name)
                            now = time.time()
                            if net_spread >= MIN_NET_SPREAD and now - last_alert.get(key, 0) >= COOLDOWN_SECONDS:
                                profit = net_proceeds - net_cost - (spend * SAFETY_MARGIN)
                                message = (
                                    f"🚨 Oportunidade potencial — {symbol}\n"
                                    f"Comprar: {buy_name}\nVender: {sell_name}\n"
                                    f"Capital de referência: {spend:.2f} USDT\n"
                                    f"Spread líquido estimado (com margem): {net_spread*100:.3f}%\n"
                                    f"Resultado estimado: {profit:.2f} USDT\n"
                                    "⚠️ Estimativa baseada no livro. Confirme saldos, taxas e execução. "
                                    "Transferências e impostos não incluídos."
                                )
                                await telegram(session, message)
                                last_alert[key] = now
                    except Exception:
                        logging.exception("Falha ao processar %s", symbol)
                await asyncio.sleep(POLL_SECONDS)
        finally:
            await asyncio.gather(binance.close(), bybit.close(), return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())
