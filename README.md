# Dineshfx - Forex & Commodities Algorithmic Trading Hub

A repository of institutional algorithmic trading strategies for **MetaTrader 5 (MT5)** and **TradingView**, optimized for **XAUUSD (Gold)**, Commodities, and Forex majors on **Vantage Markets** and **CPT Markets**.

---

## Active Strategy Catalog

| # | Strategy Name | Asset | Timeframe | Strategy Logic | Win Rate | Profit Factor | 13.5-Mo Net Return | Status |
| :---: | :--- | :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **01** | [**London Liquidity Sweep & NY Reversal**](strategies/01_London_Sweep_NY_Reversal/) | **XAUUSD** | **M5** | Institutional Judas Swing / Mean Reversion to 50% Midpoint + Profit Lock | **38.5%** | **1.62** | **+70.9 R (+70.9%)** | **Production** |

---

## Repository Structure

```text
Dineshfx/
├── README.md                                  # Repository overview and strategy index
├── .gitignore                                 # Git rules for MT5 & binary caches
└── strategies/
    └── 01_London_Sweep_NY_Reversal/           # Production Strategy: Liquidity Sweep & Mean Reversion
        ├── README.md                          # Full strategy mechanics & backtest report
        ├── mql5/                              # MetaTrader 5 source & compiled binaries
        │   ├── London_Sweep_NY_Reversal_EA.mq5
        │   ├── London_Sweep_NY_Reversal_EA.ex5
        │   ├── London_Sweep_NY_Reversal_Indicator.mq5
        │   └── London_Sweep_NY_Reversal_Indicator.ex5
        └── tradingview/                       # TradingView Pine Script v6
            └── London_Sweep_NY_Reversal.pine
```

---

## Broker Time Synchronization (Vantage Markets & CPT Markets)

Vantage Markets and CPT Markets MT5 servers run on **GMT+2 / GMT+3** (Cyprus server time, consistently **+7 hours ahead of New York EST**):

| Phase | US Eastern Time (EST/EDT) | Broker Server Time (GMT+3) | Parameter in EA / Indicator |
| :--- | :--- | :--- | :--- |
| **London Core Range Start** | 04:00 AM | **11:00** | `InpRangeStartTime = "11:00"` |
| **Pre-NY Freeze (5 min before NY)** | 08:55 AM | **15:55** | `InpRangeEndTime = "15:55"` |
| **NY Sweep Window Open** | 09:00 AM | **16:00** | `InpTradeStartTime = "16:00"` |
| **NY Sweep Window Close** | 11:30 AM | **18:30** | `InpTradeEndTime = "18:30"` |

---

## License
MIT License. Developed for algorithmic automated execution and backtesting on MetaTrader 5 and TradingView.
