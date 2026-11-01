"""Risk management: position sizing and kill-switches."""
import time
from dataclasses import dataclass, field


@dataclass
class RiskManager:
    budget: float
    leverage: float = 3.0
    risk_per_trade: float = 0.005
    max_daily_loss: float = 0.02
    max_trades_per_day: int = 40
    cooldown_sec: int = 60
    day: str = ""
    day_pnl: float = 0.0
    day_trades: int = 0
    last_close_ts: float = 0.0
    halted: bool = False

    def _roll_day(self):
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if today != self.day:
            self.day, self.day_pnl, self.day_trades, self.halted = today, 0.0, 0, False

    def can_trade(self) -> tuple[bool, str]:
        self._roll_day()
        if self.halted or self.day_pnl <= -self.max_daily_loss * self.budget:
            self.halted = True
            return False, "daily loss limit hit"
        if self.day_trades >= self.max_trades_per_day:
            return False, "max trades/day"
        if time.time() - self.last_close_ts < self.cooldown_sec:
            return False, "cooldown"
        return True, ""

    def size(self, entry: float, stop: float) -> float:
        """Base-asset quantity so that hitting the stop loses risk_per_trade*budget,
        capped so notional never exceeds budget*leverage."""
        risk_per_unit = abs(entry - stop)
        if risk_per_unit <= 0:
            return 0.0
        qty = (self.budget * self.risk_per_trade) / risk_per_unit
        # futures: notional capped at budget*leverage (5% margin buffer for fees)
        return min(qty, self.budget * self.leverage * 0.95 / entry)

    def record(self, pnl: float):
        self._roll_day()
        self.day_pnl += pnl
        self.day_trades += 1
        self.last_close_ts = time.time()
