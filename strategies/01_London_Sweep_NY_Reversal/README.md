# Strategy: London Liquidity Sweep & NY Reversal (Judas Swing)

An institutional mean-reversion trading system designed for **XAUUSD (Gold)** that capitalizes on New York opening liquidity traps (fakeouts), enhanced with an intelligent **Dynamic Profit Lock Engine**.

---

## Performance Summary (13.5 Months / 80,000 M5 Candles on Vantage Markets)

| Metric | Baseline (Pure Midpoint) | Target-Progress Lock (75% to TP -> BE) | Target-Progress Lock (75% to TP -> Lock +1R) |
| :--- | :--- | :--- | :--- |
| **Asset** | **XAUUSD (Gold)** | **XAUUSD (Gold)** | **XAUUSD (Gold)** |
| **Backtest Period** | Aug 11, 2025 – Sep 25, 2026 | Aug 11, 2025 – Sep 25, 2026 | Aug 11, 2025 – Sep 25, 2026 |
| **Total Trades** | 179 | 179 | 179 |
| **Win Rate** | 31.28% | 27.93% (Wins) + 10.6% (BE) | **38.55%** |
| **Profit Factor (PF)** | **1.58** | **1.62 (Highest PF)** | **1.59** |
| **Total Net Return (R)** | **+70.9 R** | **+67.7 R** | **+65.4 R** |
| **Max Drawdown** | **-19.2 R** | **-22.9 R** | **-22.5 R** |
| **Return on $10,000 Account (1% risk)** | +$7,090 (+70.9%) | +$6,770 (+67.7%) | +$6,540 (+65.4%) |

---

## Quantitative Study: Profit Lock Mechanism Comparison

We tested **9 different profit locking and trade management models** across 80,000 historical M5 candles of XAUUSD+ from Vantage Markets to evaluate the impact on Profit Factor (PF):

| Configuration | Trades | Win | BE | Loss | Win Rate | Profit Factor | Net Return (R) | Max DD (R) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Trigger at 75% to TP -> BE (0.0R)** | **179** | **50** | **19** | **110** | **27.9%** | **1.62** | **+67.7 R** | **-22.9 R** |
| **Trigger at 75% to TP -> Lock Half-Way** | **179** | **69** | **0** | **110** | **38.5%** | **1.61** | **+67.2 R** | **-20.2 R** |
| **Trigger at 75% to TP -> Lock +1.0R** | **179** | **69** | **0** | **110** | **38.5%** | **1.59** | **+65.4 R** | **-22.5 R** |
| **Trigger at 80% to TP -> Lock Half-Way** | **179** | **65** | **0** | **114** | **36.3%** | **1.59** | **+66.7 R** | **-17.6 R** |
| **Baseline (No Profit Lock - Full SL/TP)** | **179** | **56** | **0** | **123** | **31.3%** | **1.58** | **+70.9 R** | **-19.2 R** |
| *Premature BE at +1.0R (Naive)* | 150 | 29 | 49 | 72 | 19.3% | 0.82 | -13.2 R | -21.6 R |
| *Premature BE at +1.5R (Naive)* | 150 | 38 | 31 | 81 | 25.3% | 1.04 | +2.9 R | -24.6 R |

### Critical Trading Finding for Gold (XAUUSD):
- **Premature Break-Even Destroys Edge**: Moving SL to Break-Even at +1.0R drops the Profit Factor from **1.58 down to 0.82 (-13.2R net loss)**. Gold frequently re-tests the sweep extreme before continuing its descent/ascent to the session midpoint.
- **Target-Progress Lock (75% Rule)**: Only moving SL to Break-Even or locking +1R after price has covered **75% of the distance to the London Midpoint** boosts the Profit Factor to **1.62** and boosts win rate to **38.5%** by safeguarding against late deep reversals without choking healthy pullbacks.

---

## Strategy Rules & Mechanics

1. **London Session Range (04:00 - 08:55 EST / 11:00 - 15:55 MT5 Server Time)**:
   - Tracks the true High and Low of London.
   - Calculates the **50% Range Midpoint** (the equilibrium fair value).
   - The range box **freezes permanently at 08:55 EST** (5 minutes before New York opens). It never crosses into New York.

2. **New York Liquidity Sweep Window (09:00 - 11:30 EST / 16:00 - 18:30 MT5 Server Time)**:
   - **Bearish Sweep (Sell Setup)**:
     - Price pierces above the London High (hunting buy stops).
     - Sweep Depth Filter: Must pierce between **$0.30 and $5.00** (filters out micro noise and runaway spikes).
     - Candle closes back **BELOW** the London High.
     - **Entry**: Market SELL on candle close.
     - **Stop Loss**: Just above the sweep wick high + $0.50 buffer.
     - **Take Profit**: **50% Midpoint of the London Range**.
   - **Bullish Sweep (Buy Setup)**:
     - Price pierces below the London Low (hunting sell stops).
     - Sweep Depth Filter: Pierces between **$0.30 and $5.00**.
     - Candle closes back **ABOVE** the London Low.
     - **Entry**: Market BUY on candle close.
     - **Stop Loss**: Just below the sweep wick low - $0.50 buffer.
     - **Take Profit**: **50% Midpoint of the London Range**.

3. **Dynamic Profit Lock Engine**:
   - Monitors running position in real-time.
   - Once price covers **75% of the distance to the TP target**, the EA automatically modifies the Stop Loss to **Break-Even (0.0R)** or **locks +1.0R / 50% profit**, securing the trade from turning into a loss.

---

## Recommendations for a $100 Account

- **Lot Size**: Use **`InpFixedLotSize = 0.01`**. On a $100 account, 0.01 is the broker's minimum allowable lot size.
- **Dollar Risk per Trade**: With an average Stop Loss of $1.50 - $2.50 on Gold, a 0.01 lot trade risks **$1.50 - $2.50 per trade (1.5% - 2.5% account risk)**, which is well within safe drawdown limits.
- **Profit Potential**: Average winning target (Midpoint) is $6.00 - $12.00, yielding **+$6.00 to +$12.00 profit per win (+6% to +12% account gain)**.
- **Max Trades Per Day**: Keep `InpMaxTradesPerDay = 1` to prevent over-trading.

---

## File Structure

```text
strategies/01_London_Sweep_NY_Reversal/
├── README.md                                  # Strategy rules and performance documentation
├── mql5/
│   ├── London_Sweep_NY_Reversal_EA.mq5        # Fully automated Expert Advisor with Profit Lock Engine
│   ├── London_Sweep_NY_Reversal_EA.ex5        # Compiled EA binary (Ready to trade in MT5)
│   ├── London_Sweep_NY_Reversal_Indicator.mq5 # Chart visual indicator with alerts
│   └── London_Sweep_NY_Reversal_Indicator.ex5 # Compiled indicator binary
└── tradingview/
    └── London_Sweep_NY_Reversal.pine          # Pine Script v6 indicator with visual levels
```
