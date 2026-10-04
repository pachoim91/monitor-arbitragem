import os, time, asyncio, logging
import aiohttp
import ccxt.async_support as ccxt

# Configure these as environment variables in your hosting service.
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CAPITAL_USDT = float(os.getenv("CAPITAL_USDT", "350"))
MIN_NET_SPREAD = float(os.getenv("MIN_NET_SPREAD", "0.005"))  # 0.5%
FEE_BUY = float(os.getenv("FEE_BUY", "0.001"))               # 0.10%
FEE_SELL = float(os.getenv("FEE_SELL", "0.001"))             # 0.10%
SAFETY_MARGIN = float(os.getenv("SAFETY_MARGIN", "0.001"))   # 0.10%
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "8"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "900"))
SYMBOLS = os.getenv("SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT").split(",")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

async def telegram(session, message):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    async with session.post(url, data={"chat_id": CHAT_ID, "text": message}) as r:
        if r.status != 200:
            logging.warning("Telegram returned HTTP %s", r.status)

def executable_vwap(levels, quote_budget):
    """Buy/sell quote amount across visible order-book levels; return base qty and quote used/received."""
    remaining=quote_budget
    base=0.0
    quote=0.0
    for price, amount in levels:
        if price <= 0 or amount <= 0: continue
        take=min(amount, remaining/price)
        base += take
        quote += take*price
        remaining -= take*price
        if remaining <= 1e-8: break
    if remaining > max(0.01, quote_budget*0.001):
        return None
    return base, quote

async def main():
    binance=ccxt.binance({"enableRateLimit": True, "options":{"defaultType":"spot"}})
    bybit=ccxt.bybit({"enableRateLimit": True, "options":{"defaultType":"spot"}})
    last_alert={}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        await telegram(session, "🤖 Monitor de arbitragem iniciado. Somente alertas; nenhuma ordem será enviada.")
        try:
            await asyncio.gather(binance.load_markets(), bybit.load_markets())
            while True:
                for symbol in SYMBOLS:
                    symbol=symbol.strip()
                    try:
                        if symbol not in binance.markets or symbol not in bybit.markets:
                            logging.info("Par indisponível: %s", symbol); continue
                        ob_a, ob_b = await asyncio.gather(
                            binance.fetch_order_book(symbol, limit=20),
                            bybit.fetch_order_book(symbol, limit=20))
                        # Both directions: buy asks on one venue, sell bids on the other.
                        candidates=[
                            ("Binance", "Bybit", ob_a["asks"], ob_b["bids"]),
                            ("Bybit", "Binance", ob_b["asks"], ob_a["bids"])
                        ]
                        for buy_name, sell_name, asks, bids in candidates:
                            buy=executable_vwap(asks, CAPITAL_USDT)
                            if not buy: continue
                            qty, spend=buy
                            # Sell the same base quantity, walking bid levels.
                            remaining=qty; proceeds=0.0
                            for price, amount in bids:
                                take=min(amount, remaining)
                                proceeds += take*price
                                remaining -= take
                                if remaining <= 1e-12: break
                            if remaining > max(1e-10, qty*0.001): continue
                            net_proceeds=proceeds*(1-FEE_SELL)
                            net_cost=spend*(1+FEE_BUY)
                            net_spread=(net_proceeds-net_cost)/net_cost-SAFETY_MARGIN
                            key=(symbol,buy_name,sell_name)
                            now=time.time()
                            if net_spread >= MIN_NET_SPREAD and now-last_alert.get(key,0)>=COOLDOWN_SECONDS:
                                profit=net_proceeds-net_cost-(spend*SAFETY_MARGIN)
                                msg=(f"🚨 Oportunidade potencial — {symbol}\n"
                                     f"Comprar: {buy_name}\nVender: {sell_name}\n"
                                     f"Capital de referência: {spend:.2f} USDT\n"
                                     f"Spread líquido estimado (com margem): {net_spread*100:.3f}%\n"
                                     f"Resultado estimado: {profit:.2f} USDT\n"
                                     "⚠️ Cotação de livro; confirme saldos, taxas reais e execução. "
                                     "Transferências e impostos não incluídos.")
                                await telegram(session,msg)
                                last_alert[key]=now
                    except Exception as e:
                        logging.warning("%s %s: %s", symbol, type(e).__name__, e)
                await asyncio.sleep(POLL_SECONDS)
        finally:
            await asyncio.gather(binance.close(),bybit.close())

if __name__ == "__main__":
    asyncio.run(main())
