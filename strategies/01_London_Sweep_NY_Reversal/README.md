# Strategy: London Liquidity Sweep & NY Reversal (Judas Swing)

An institutional mean-reversion trading system designed for **XAUUSD (Gold)** that capitalizes on New York opening liquidity traps (fakeouts).

---

## Performance Summary (13.5 Months / 80,000 M5 Candles on Vantage Markets)

| Metric | Result |
| :--- | :--- |
| **Asset** | **XAUUSD (Gold)** |
| **Backtest Period** | August 11, 2025 – September 25, 2026 |
| **Total Trades** | 179 |
| **Win Rate** | **31.28%** |
| **Profit Factor** | **1.58** |
| **Total Net Return (R)** | **+70.9 R** |
| **Return on $10,000 Account (1% risk)** | **+$7,090 (+70.9% Net Gain)** |
| **Max Drawdown** | **-19.2 R** |

---

## Strategy Rules & Mechanics

1. **London Session Range (04:00 - 08:55 EST / 11:00 - 15:55 MT5 Server Time)**:
   - Tracks the true High and Low of London.
   - Calculates the **50% Range Midpoint** (the equilibrium fair value).
   - The range box **freezes permanently at 08:55 EST** (5 minutes before New York opens). It never crosses into New York.

2. **New York Liquidity Sweep Window (09:00 - 11:30 EST / 16:00 - 18:30 MT5 Server Time)**:
   - **Bearish Sweep (Sell Setup)**:
     - Price pierces above the London High (hunting buy stops).
     - Sweep Depth Filter: Must pierce between **$0.30 and $5.00** (filters out double tops and runaway news).
     - The candle closes back **BELOW** the London High with a **bearish close (`Close < Open`)**.
     - **Entry**: Market SELL on candle close.
     - **Stop Loss**: Just above the sweep wick high + $0.50 buffer.
     - **Take Profit**: **50% Midpoint of the London Range** (average reward is +4R to +8R!).
   - **Bullish Sweep (Buy Setup)**:
     - Price pierces below the London Low (hunting sell stops).
     - Sweep Depth Filter: Pierces between **$0.30 and $5.00**.
     - Candle closes back **ABOVE** the London Low with a **bullish close (`Close > Open`)**.
     - **Entry**: Market BUY on candle close.
     - **Stop Loss**: Just below the sweep wick low - $0.50 buffer.
     - **Take Profit**: **50% Midpoint of the London Range**.

---

## File Structure

```text
strategies/01_London_Sweep_NY_Reversal/
├── README.md                                  # Strategy rules and performance documentation
├── mql5/
│   ├── London_Sweep_NY_Reversal_EA.mq5        # Fully automated Expert Advisor
│   ├── London_Sweep_NY_Reversal_EA.ex5        # Compiled EA binary (Ready to trade)
│   ├── London_Sweep_NY_Reversal_Indicator.mq5 # Chart visual indicator with alerts
│   └── London_Sweep_NY_Reversal_Indicator.ex5 # Compiled indicator binary
└── tradingview/
    └── London_Sweep_NY_Reversal.pine          # Pine Script v6 indicator with visual levels
```
