"""Automated scalping bot.

MODE=paper (default): real market data, simulated fills. No keys needed.
MODE=live: real orders. Requires API keys AND --i-understand-the-risk.
Long-only spot. One position at a time. Exits are managed by the bot
(market order on stop/target) so it works on any exchange.
"""
import argparse
import logging
import os
import signal
import sys
import time

import ccxt

from risk import RiskManager
from strategy import Params, entry_signal

log = logging.getLogger("scalper")


def env(k, d):
    return os.getenv(k, d)


def load_dotenv(path=".env"):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.split("#")[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


class Broker:
    def __init__(self, ex, symbol, live, fee):
        self.ex, self.symbol, self.live, self.fee = ex, symbol, live, fee

    def price(self):
        return self.ex.fetch_ticker(self.symbol)["last"]

    def buy(self, qty):
        qty = float(self.ex.amount_to_precision(self.symbol, qty))
        if self.live:
            o = self.ex.create_market_buy_order(self.symbol, qty)
            o = self.ex.fetch_order(o["id"], self.symbol)
            return o["average"] or self.price(), o["filled"] or qty
        return self.price(), qty

    def sell(self, qty):
        if self.live:
            o = self.ex.create_market_sell_order(self.symbol, qty)
            o = self.ex.fetch_order(o["id"], self.symbol)
            return o["average"] or self.price()
        return self.price()


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--i-understand-the-risk", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    live = env("MODE", "paper") == "live"
    if live and not args.i_understand_the_risk:
        sys.exit("MODE=live needs --i-understand-the-risk")
    symbol, tf = env("SYMBOL", "BTC/USDT"), env("TIMEFRAME", "1m")
    fee = float(env("FEE_RATE", "0.001"))

    cfg = {"enableRateLimit": True}
    if env("API_KEY", ""):
        cfg.update(apiKey=env("API_KEY", ""), secret=env("API_SECRET", ""))
    ex = getattr(ccxt, env("EXCHANGE", "binance"))(cfg)
    if env("SANDBOX", "1") == "1" and live:
        ex.set_sandbox_mode(True)
    ex.load_markets()

    rm = RiskManager(
        budget=float(env("QUOTE_BUDGET", "100")),
        risk_per_trade=float(env("RISK_PER_TRADE", "0.005")),
        max_daily_loss=float(env("MAX_DAILY_LOSS", "0.02")),
        max_trades_per_day=int(env("MAX_TRADES_PER_DAY", "40")),
        cooldown_sec=int(env("COOLDOWN_SEC", "60")),
    )
    br, params = Broker(ex, symbol, live, fee), Params()
    pos = None  # dict(qty, entry, stop, target)
    stop_flag = {"v": False}
    signal.signal(signal.SIGINT, lambda *_: stop_flag.update(v=True))
    signal.signal(signal.SIGTERM, lambda *_: stop_flag.update(v=True))
    log.info("start mode=%s symbol=%s budget=%s sandbox=%s",
             "LIVE" if live else "paper", symbol, rm.budget, env("SANDBOX", "1"))

    last_candle_ts = 0
    while not stop_flag["v"]:
        try:
            if pos:  # manage open position every few seconds
                px = br.price()
                reason = "stop" if px <= pos["stop"] else "target" if px >= pos["target"] else None
                if reason:
                    out = br.sell(pos["qty"])
                    pnl = pos["qty"] * (out - pos["entry"]) - fee * pos["qty"] * (out + pos["entry"])
                    rm.record(pnl)
                    log.info("EXIT %s @%.4f pnl=%.4f day_pnl=%.4f", reason, out, pnl, rm.day_pnl)
                    pos = None
                time.sleep(2)
                continue

            candles = ex.fetch_ohlcv(symbol, tf, limit=300)[:-1]  # drop forming candle
            if candles and candles[-1][0] != last_candle_ts:
                last_candle_ts = candles[-1][0]
                ok, why = rm.can_trade()
                sig = entry_signal(candles, params) if ok else None
                if sig:
                    qty = rm.size(sig.entry, sig.stop)
                    if qty > 0:
                        entry, filled = br.buy(qty)
                        shift = entry - sig.entry
                        pos = dict(qty=filled, entry=entry,
                                   stop=sig.stop + shift, target=sig.target + shift)
                        log.info("ENTRY @%.4f qty=%.6f sl=%.4f tp=%.4f",
                                 entry, filled, pos["stop"], pos["target"])
                elif not ok and why == "daily loss limit hit":
                    log.warning("halted: %s", why)
            time.sleep(5)
        except (ccxt.NetworkError, ccxt.RequestTimeout) as e:
            log.warning("network: %s", e); time.sleep(10)
        except ccxt.ExchangeError as e:
            log.error("exchange: %s", e); time.sleep(15)

    if pos:  # graceful shutdown: never leave a position unmanaged
        out = br.sell(pos["qty"])
        log.info("shutdown: closed position @%.4f", out)
    log.info("stopped")


if __name__ == "__main__":
    main()
