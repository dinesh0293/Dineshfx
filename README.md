# New York Open (9:30 AM EST) Breakout Strategy - MetaTrader 5

An automated and indicator-assisted **Opening Range Breakout (ORB)** system for MetaTrader 5, tailored for **XAUUSD (Gold)** and US equity indices (US30, NAS100) on brokers like **Vantage Markets** and **CPT Markets**.

---

## Strategy Rules

1. **Pre-Market Range Box**:
   - High and Low are marked between **8:00 AM – 9:25 AM EST** (Broker server time **15:00 – 16:25** on GMT+2/GMT+3 brokers).
2. **Breakout Signal**:
   - The US New York session opens at **9:30 AM EST** (**16:30 Broker Time**).
   - Wait for a 5-minute candle (**M5**) to **close cleanly** outside the pre-market box:
     - **Buy Signal**: `Close[1] > RangeHigh` and `Open[1] <= RangeHigh`.
     - **Sell Signal**: `Close[1] < RangeLow` and `Open[1] >= RangeLow`.
3. **Risk Management & Exit**:
   - **Stop Loss**: Placed below/above the breakout candle (with buffer) or at the box midpoint.
   - **Take Profit**: Calculated from Stop Loss distance using a strict Risk-to-Reward ratio (e.g., 1:2 R:R).
   - **Trade Frequency**: Strictly max 1 trade per day.

---

## Time Conversion (Vantage & CPT Markets)

| Phase | US Eastern Time (EST/EDT) | Broker Server Time (GMT+2 / GMT+3) | Parameter |
| :--- | :--- | :--- | :--- |
| **Range Start** | 8:00 AM | **15:00** | `InpRangeStartTime = "15:00"` |
| **Range End** | 9:25 AM | **16:25** | `InpRangeEndTime = "16:25"` |
| **Trade Window Open** | 9:30 AM | **16:30** | `InpTradeStartTime = "16:30"` |
| **Trade Window Close** | 10:15 AM | **17:15** | `InpTradeEndTime = "17:15"` |

---

## Project Structure

```text
NY_Open_Breakout_MT5/
├── NY_Open_Breakout_EA.mq5        # Full automated Expert Advisor source code
├── NY_Open_Breakout_EA.ex5        # Compiled executable EA binary
├── NY_Open_Range_Indicator.mq5    # Chart visual box & alert indicator source code
├── NY_Open_Range_Indicator.ex5    # Compiled indicator binary
├── .gitignore                     # Git ignore rules for MT5
└── README.md                      # Documentation & user guide
```

---

## Installation & Deployment

### 1. MT5 Folder Locations
- Place `NY_Open_Range_Indicator.ex5` into:  
  `[MT5 Data Folder]\MQL5\Indicators\`
- Place `NY_Open_Breakout_EA.ex5` into:  
  `[MT5 Data Folder]\MQL5\Experts\`

### 2. Chart Setup
1. Open an **`XAUUSD`** chart on the **`M5`** timeframe.
2. Drag `NY_Open_Breakout_EA` onto the chart.
3. In the **Common** tab, check **"Allow Algo Trading"**.
4. In the top toolbar, ensure the **"Algo Trading"** master switch is **Green**.

---

## License
MIT License. For educational and automated algorithmic trading purposes. Always test on demo accounts before deploying on live capital.
