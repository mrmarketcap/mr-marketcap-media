"""Automated scalping bot.

MODE=paper (default): real market data, simulated fills. No keys needed.
MODE=live: real orders. Requires API keys AND --i-understand-the-risk.
OKX USDT-margined perpetual (BNB/USDT:USDT), isolated margin, long + short.
One position at a time. Take-profit is managed by the bot; the stop-loss is
also placed on the exchange as a reduce-only trigger order.
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


def env(k, d):  # noqa
    return os.getenv(k, d)


def load_dotenv(path=".env"):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.split("#")[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


class Broker:
    """OKX perpetual swap, isolated margin, net (one-way) position mode."""

    def __init__(self, ex, symbol, live, leverage):
        self.ex, self.symbol, self.live, self.lev = ex, symbol, live, leverage
        self.cs = ex.market(symbol).get("contractSize") or 1.0
        self.p = {"tdMode": "isolated"}

    def setup(self):
        if not self.live:
            return
        try:
            self.ex.set_position_mode(False, self.symbol)
        except ccxt.ExchangeError as e:
            log.warning("position mode: %s", e)
        self.ex.set_leverage(self.lev, self.symbol, {"mgnMode": "isolated"})

    def open_contracts(self):
        if not self.live:
            return 0.0
        return sum(abs(p["contracts"] or 0) for p in self.ex.fetch_positions([self.symbol]))

    def price(self):
        return self.ex.fetch_ticker(self.symbol)["last"]

    def contracts(self, base_qty):
        return float(self.ex.amount_to_precision(self.symbol, base_qty / self.cs))

    def enter(self, side, base_qty, stop):
        n = self.contracts(base_qty)
        if n <= 0:
            return None
        if not self.live:
            return dict(entry=self.price(), n=n, sl_id=None)
        o = self.ex.create_order(self.symbol, "market", "buy" if side == "long" else "sell", n, None, self.p)
        o = self.ex.fetch_order(o["id"], self.symbol)
        entry = o.get("average") or self.price()
        n = o.get("filled") or n
        try:  # exchange-side stop: protects you even if the bot/server dies
            sl = self.ex.create_order(
                self.symbol, "market", "sell" if side == "long" else "buy", n, None,
                {**self.p, "reduceOnly": True, "stopLossPrice": float(self.ex.price_to_precision(self.symbol, stop))})
            sl_id = sl["id"]
        except ccxt.BaseError as e:
            log.error("stop-loss order failed (%s) -> closing position for safety", e)
            self.exit(side, n, None)
            return None
        return dict(entry=entry, n=n, sl_id=sl_id)

    def exit(self, side, n, sl_id):
        if not self.live:
            return self.price()
        if sl_id:
            try:
                self.ex.cancel_order(sl_id, self.symbol, {"stop": True})
            except ccxt.BaseError as e:
                log.warning("cancel stop: %s", e)
        o = self.ex.create_order(self.symbol, "market", "sell" if side == "long" else "buy", n, None,
                                 {**self.p, "reduceOnly": True})
        o = self.ex.fetch_order(o["id"], self.symbol)
        return o.get("average") or self.price()


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--i-understand-the-risk", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    live = env("MODE", "paper") == "live"
    if live and not args.i_understand_the_risk:
        sys.exit("MODE=live needs --i-understand-the-risk")
    symbol, tf = env("SYMBOL", "BNB/USDT:USDT"), env("TIMEFRAME", "1m")
    fee = float(env("FEE_RATE", "0.0005"))

    cfg = {"enableRateLimit": True}
    if env("API_KEY", ""):
        cfg.update(apiKey=env("API_KEY", ""), secret=env("API_SECRET", ""), password=env("API_PASSPHRASE", ""))
    ex = getattr(ccxt, env("EXCHANGE", "okx"))(cfg)
    if env("SANDBOX", "1") == "1" and live:
        ex.set_sandbox_mode(True)
    ex.load_markets()

    lev = float(env("LEVERAGE", "3"))
    if lev > 5:
        sys.exit("LEVERAGE > 5 refused by safety check")
    rm = RiskManager(
        budget=float(env("QUOTE_BUDGET", "100")), leverage=lev,
        risk_per_trade=float(env("RISK_PER_TRADE", "0.005")),
        max_daily_loss=float(env("MAX_DAILY_LOSS", "0.02")),
        max_trades_per_day=int(env("MAX_TRADES_PER_DAY", "40")),
        cooldown_sec=int(env("COOLDOWN_SEC", "60")),
    )
    br, params = Broker(ex, symbol, live, lev), Params()
    if live:
        if not (cfg.get("apiKey") and cfg.get("password")):
            sys.exit("live mode needs API_KEY, API_SECRET, API_PASSPHRASE")
        if br.open_contracts():
            sys.exit("an open position already exists on this symbol; close it first")
    br.setup()
    pos = None  # dict(side, n, qty, entry, stop, target, sl_id)
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
                d = 1 if pos["side"] == "long" else -1
                hit_sl = px <= pos["stop"] if d == 1 else px >= pos["stop"]
                hit_tp = px >= pos["target"] if d == 1 else px <= pos["target"]
                reason = "stop" if hit_sl else "target" if hit_tp else None
                if live and not reason and br.open_contracts() == 0:
                    reason, px = "stop(exchange)", pos["stop"]  # exchange SL already closed it
                    out = px
                elif reason:
                    out = br.exit(pos["side"], pos["n"], pos["sl_id"])
                if reason:
                    pnl = d * pos["qty"] * (out - pos["entry"]) - fee * pos["qty"] * (out + pos["entry"])
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
                    r = br.enter(sig.side, qty, sig.stop) if qty > 0 else None
                    if r:
                        shift = r["entry"] - sig.entry
                        pos = dict(side=sig.side, n=r["n"], qty=r["n"] * br.cs, entry=r["entry"],
                                   stop=sig.stop + shift, target=sig.target + shift, sl_id=r["sl_id"])
                        log.info("ENTRY %s @%.4f contracts=%s sl=%.4f tp=%.4f", sig.side.upper(),
                                 r["entry"], r["n"], pos["stop"], pos["target"])
                elif not ok and why == "daily loss limit hit":
                    log.warning("halted: %s", why)
            time.sleep(5)
        except (ccxt.NetworkError, ccxt.RequestTimeout) as e:
            log.warning("network: %s", e); time.sleep(10)
        except ccxt.ExchangeError as e:
            log.error("exchange: %s", e); time.sleep(15)

    if pos:  # graceful shutdown: never leave a position unmanaged
        out = br.exit(pos["side"], pos["n"], pos["sl_id"])
        log.info("shutdown: closed position @%.4f", out)
    log.info("stopped")


if __name__ == "__main__":
    main()
