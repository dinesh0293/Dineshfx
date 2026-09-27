# Dineshfx - Forex & Commodities Trading Strategy Hub

A centralized repository for systematic, automated, and algorithmic trading strategies across **Forex** and **Commodities** (Gold / XAUUSD, Silver, US Indices, Majors).

Each strategy in this repository is packaged with:
- **MetaTrader 5 (MT5)** automated Expert Advisors (EAs) and indicators (`.mq5` / `.ex5`).
- **TradingView** Pine Script v5 indicators (`.pine`).
- Comprehensive documentation, session times, broker GMT mapping (Vantage Markets & CPT Markets), and risk management rules.

---

## Strategy Catalog

| # | Strategy Name | Primary Instruments | Timeframe | Platforms | Status |
| :---: | :--- | :--- | :---: | :--- | :---: |
| **01** | [**NY Open (9:30 AM EST) Breakout**](strategies/01_NY_Open_Breakout/) | XAUUSD (Gold), US30, NAS100 | M5 | MT5 (EA + Indicator) & TradingView | **Active** |
| **02** | *Upcoming Strategy* | TBD | TBD | MT5 & TradingView | Planned |
| **03** | *Upcoming Strategy* | TBD | TBD | MT5 & TradingView | Planned |

---

## Repository Structure

```text
Dineshfx/
├── README.md                                  # Repository overview and strategy index
├── .gitignore                                 # Git rules for MT5 & trading files
└── strategies/
    └── 01_NY_Open_Breakout/                   # New York Open ORB Strategy
        ├── README.md                          # Strategy documentation & parameter guide
        ├── mql5/                              # MetaTrader 5 source & binaries
        │   ├── NY_Open_Breakout_EA.mq5        # Automated Expert Advisor
        │   ├── NY_Open_Breakout_EA.ex5        # Compiled EA binary
        │   ├── NY_Open_Range_Indicator.mq5    # Session box & alert indicator
        │   └── NY_Open_Range_Indicator.ex5    # Compiled indicator binary
        └── tradingview/                       # TradingView Pine Script v5
            └── NY_Open_Breakout.pine          # Multi-session box, signals & dashboard
```

---

## How to Add New Strategies

When adding a new strategy:
1. Create a new folder under `strategies/` (e.g. `strategies/02_Strategy_Name/`).
2. Include:
   - `mql5/`: EA and indicators for MetaTrader 5.
   - `tradingview/`: Pine Script v5 code.
   - `README.md`: Entry rules, stop loss logic, and broker time mapping.
3. Update the Strategy Catalog table in this root `README.md`.

---

## Broker Compatibility
Tested and configured for:
- **Vantage Markets** (MT5 Raw / Standard - Server Time GMT+2 / GMT+3)
- **CPT Markets** (MT5 ECN / Prime - Server Time GMT+2 / GMT+3)
