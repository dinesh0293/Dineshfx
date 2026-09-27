//+------------------------------------------------------------------+
//|                                  London_Sweep_NY_Reversal_EA.mq5 |
//|                                   Copyright 2026, Dineshfx / AI |
//|                London Liquidity Sweep & NY Reversal Strategy     |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Dineshfx"
#property link      "https://github.com/dinesh0293/Dineshfx"
#property version   "2.20"
#property description "Institutional Liquidity Sweep & Mean Reversion Strategy for Gold (XAUUSD) with Dynamic Profit Lock Engine and High-Impact News Filter."

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//--- Enums
enum ENUM_TP_MODE
{
   TP_RANGE_MIDPOINT = 0, // 50% Range Midpoint (Proven +70.9R / PF 1.58 - 1.62)
   TP_FIXED_RR_2_0   = 1, // Fixed 1:2.0 Risk-to-Reward
   TP_FIXED_RR_2_5   = 2, // Fixed 1:2.5 Risk-to-Reward
   TP_OPPOSITE_RANGE = 3  // Opposite London Session Extreme
};

enum ENUM_PROFIT_LOCK_TYPE
{
   LOCK_DISABLED        = 0, // Disabled (Let run to Target or SL)
   LOCK_AT_TP_PERCENT   = 1, // Target Progress Lock (75% to Midpoint -> Proven PF 1.62)
   LOCK_AT_R_MULTIPLE   = 2, // Fixed R-Multiple Trigger (e.g. at +2.0R)
   LOCK_TRAILING_STEP   = 3  // Stepped Trailing Stop (+1.5R->BE, +2.5R->+1R, +3.5R->+2R)
};

enum ENUM_LOCK_LEVEL
{
   LOCK_TO_BREAK_EVEN   = 0, // Move SL to Exact Entry Price (0.0R)
   LOCK_TO_PLUS_HALF_R  = 1, // Move SL to Entry + 0.5R Profit
   LOCK_TO_PLUS_ONE_R   = 2, // Move SL to Entry + 1.0R Profit
   LOCK_HALF_WAY        = 3  // Move SL to Halfway of Gain (Locks 50% Profit)
};

//--- Inputs
input group "=== Session Times (Broker Server Time - Vantage GMT+3) ==="
input string                 InpRangeStartTime    = "11:00";    // London Core Range Start (04:00 AM NY)
input string                 InpRangeEndTime      = "15:55";    // Freeze 5 min before NY (08:55 AM NY)
input string                 InpTradeStartTime    = "16:00";    // NY Sweep Window Start (09:00 AM NY)
input string                 InpTradeEndTime      = "18:30";    // NY Sweep Window End (11:30 AM NY)

input group "=== Sweep Confirmation & Filters ==="
input int                    InpMinSweepPoints    = 30;         // Min Sweep Depth ($0.30 on Gold = 30 pts)
input int                    InpMaxSweepPoints    = 500;        // Max Sweep Depth ($5.00 on Gold = 500 pts)
input bool                   InpRequireDispCandle = false;      // Require Reversal Candle (False = Maximum PF 1.58-1.62)
input int                    InpSLBufferPoints    = 50;         // SL Buffer beyond sweep wick ($0.50 = 50 pts)
input ENUM_TP_MODE           InpTargetMode        = TP_RANGE_MIDPOINT; // Take Profit Mode

input group "=== Profit Lock & Trade Management ==="
input ENUM_PROFIT_LOCK_TYPE  InpProfitLockType    = LOCK_AT_TP_PERCENT; // Profit Lock Engine Mode
input double                 InpLockTriggerPct    = 75.0;              // Trigger at % of TP Progress (75% = PF 1.62)
input ENUM_LOCK_LEVEL        InpLockLevel         = LOCK_TO_BREAK_EVEN;// Lock Level when triggered
input double                 InpLockTriggerR      = 2.0;               // Trigger at R-Multiple (for R mode)
input double                 InpLockProfitFixedR  = 0.5;               // Custom R locked (for R mode)

input group "=== News Protection & Event Filters ==="
input bool                   InpFilterNFPFriday   = true;              // Auto-Block First Friday of Month (NFP Jobs Report)
input bool                   InpFilterHighNews    = true;              // Auto-Filter MT5 High-Impact USD News
input int                    InpNewsBufferMins    = 45;                // News Buffer Window (minutes before/after)
input string                 InpSkipDatesList     = "2026.10.02, 2026.10.12, 2026.10.14, 2026.10.29, 2026.11.04, 2026.11.05, 2026.11.06, 2026.11.11, 2026.11.12, 2026.11.26, 2026.11.27, 2026.12.04, 2026.12.10, 2026.12.15, 2026.12.16, 2026.12.24, 2026.12.25, 2026.12.31"; // Blacklist Dates (Q4 2026 CPI/FOMC/Holidays)
input bool                   InpShowNewsButton    = true;              // Show One-Click Pause Button on Chart

input group "=== Risk & Money Management ==="
input double                 InpRiskPercent       = 1.0;        // Risk Percentage (% of Equity)
input double                 InpFixedLotSize      = 0.0;        // Fixed Lot (0.0 = Dynamic Auto-Risk, e.g. 0.01 for $100 account)
input int                    InpMaxSpreadPoints   = 60;         // Max Allowed Spread (points)
input int                    InpMaxTradesPerDay   = 1;          // Max trades per day
input ulong                  InpMagicNumber       = 4402026;    // Magic Number
input string                 InpTradeComment      = "SWEEP_REV"; // Trade Comment

input group "=== Visuals ==="
input bool                   InpDrawBox           = true;       // Draw London Box on Chart
input color                  InpBoxColor          = clrDodgerBlue; // Range Box Color

//--- Global Variables
CTrade         m_trade;
CPositionInfo  m_position;
datetime       m_lastBarTime = 0;
int            m_tradesTodayCount = 0;

double         m_rangeHigh = 0.0;
double         m_rangeLow  = 0.0;
double         m_rangeMid  = 0.0;
bool           m_rangeFormed = false;

ulong          m_trackedTicket = 0;
double         m_trackedInitialRisk = 0.0;

bool           m_manualNewsPause = false;
string         m_newsStatusText  = "CLEAR";

//+------------------------------------------------------------------+
//| Convert "HH:MM" string to seconds from midnight                  |
//+------------------------------------------------------------------+
int TimeToSecondsOfDay(string timeStr)
{
   string parts[];
   int count = StringSplit(timeStr, ':', parts);
   if(count >= 2)
   {
      int h = (int)StringToInteger(parts[0]);
      int m = (int)StringToInteger(parts[1]);
      return (h * 3600 + m * 60);
   }
   return 0;
}

//+------------------------------------------------------------------+
//| Check if today is the first Friday of the month (NFP Day)        |
//+------------------------------------------------------------------+
bool IsNFPFriday(datetime time)
{
   if(!InpFilterNFPFriday) return false;
   MqlDateTime dt;
   TimeToStruct(time, dt);
   // Day of week: 5 = Friday. If day of month is between 1 and 7, it is NFP day!
   if(dt.day_of_week == 5 && dt.day <= 7)
      return true;
   return false;
}

//+------------------------------------------------------------------+
//| Check if today's date is in the user blacklist list              |
//+------------------------------------------------------------------+
bool IsDateBlacklisted(datetime time, string datesList)
{
   if(StringLen(datesList) == 0) return false;
   string todayStr = TimeToString(time, TIME_DATE); // "YYYY.MM.DD"
   string dates[];
   int count = StringSplit(datesList, ',', dates);
   for(int i = 0; i < count; i++)
   {
      string d = dates[i];
      StringTrimLeft(d);
      StringTrimRight(d);
      if(d == todayStr) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Check MT5 Economic Calendar for High-Impact USD Events           |
//+------------------------------------------------------------------+
bool IsHighImpactUSDNewsNear(int bufferMinutes, string &eventNameOut)
{
   if(!InpFilterHighNews) return false;

   datetime now = TimeCurrent();
   datetime from = now - (bufferMinutes * 60);
   datetime to   = now + (bufferMinutes * 60);

   MqlCalendarValue values[];
   int count = CalendarValueHistory(values, from, to, "US");
   if(count > 0)
   {
      for(int i = 0; i < count; i++)
      {
         MqlCalendarEvent event;
         if(CalendarEventById(values[i].event_id, event))
         {
            if(event.importance == CALENDAR_IMPORTANCE_HIGH)
            {
               eventNameOut = event.name;
               return true;
            }
         }
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Create or update on-chart One-Click Pause Button                 |
//+------------------------------------------------------------------+
void UpdatePauseButton()
{
   if(!InpShowNewsButton) return;

   string btnName = "SWEEP_EA_BtnPause";
   if(ObjectFind(0, btnName) < 0)
   {
      ObjectCreate(0, btnName, OBJ_BUTTON, 0, 0, 0);
      ObjectSetInteger(0, btnName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, btnName, OBJPROP_XDISTANCE, 20);
      ObjectSetInteger(0, btnName, OBJPROP_YDISTANCE, 70);
      ObjectSetInteger(0, btnName, OBJPROP_XSIZE, 180);
      ObjectSetInteger(0, btnName, OBJPROP_YSIZE, 30);
      ObjectSetInteger(0, btnName, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, btnName, OBJPROP_SELECTABLE, false);
   }

   if(m_manualNewsPause)
   {
      ObjectSetString(0, btnName, OBJPROP_TEXT, "⚠️ NEWS PAUSED (Click)");
      ObjectSetInteger(0, btnName, OBJPROP_BGCOLOR, clrCrimson);
      ObjectSetInteger(0, btnName, OBJPROP_COLOR, clrWhite);
   }
   else
   {
      ObjectSetString(0, btnName, OBJPROP_TEXT, "🟢 ALGO ACTIVE (Click Pause)");
      ObjectSetInteger(0, btnName, OBJPROP_BGCOLOR, clrDarkGreen);
      ObjectSetInteger(0, btnName, OBJPROP_COLOR, clrWhite);
   }
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Handle Chart Events (Button Clicks)                              |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK && sparam == "SWEEP_EA_BtnPause")
   {
      m_manualNewsPause = !m_manualNewsPause;
      PrintFormat("[EA NEWS TOGGLE] Algorithmic trading manually %s by user.", m_manualNewsPause ? "PAUSED (News Mode)" : "RESUMED");
      UpdatePauseButton();
   }
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();
   m_trade.SetTypeFillingBySymbol(_Symbol);

   UpdatePauseButton();

   Print("London_Sweep_NY_Reversal_EA v2.20 initialized on ", _Symbol, " Period: ", EnumToString(Period()));
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "SWEEP_EA_");
   Comment("");
}

//+------------------------------------------------------------------+
//| Calculate Dynamic Lot Size                                       |
//+------------------------------------------------------------------+
double CalculateLotSize(double slDistancePrice)
{
   if(InpFixedLotSize > 0.0) return InpFixedLotSize;
   if(slDistancePrice <= 0.0) return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * (InpRiskPercent / 100.0);

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(tickSize <= 0.0 || tickValue <= 0.0 || point <= 0.0)
      return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

   double pointsRisk = slDistancePrice / point;
   double moneyRiskPerLot = pointsRisk * (tickValue / (tickSize / point));
   if(moneyRiskPerLot <= 0.0) return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

   double calculatedLot = riskAmount / moneyRiskPerLot;

   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   calculatedLot = MathFloor(calculatedLot / lotStep) * lotStep;
   if(calculatedLot < lotMin) calculatedLot = lotMin;
   if(calculatedLot > lotMax) calculatedLot = lotMax;

   return calculatedLot;
}

//+------------------------------------------------------------------+
//| Count trades taken today                                         |
//+------------------------------------------------------------------+
int CountTradesToday(datetime dayStart)
{
   int count = 0;
   HistorySelect(dayStart, TimeCurrent());
   int totalDeals = HistoryDealsTotal();
   for(int i = 0; i < totalDeals; i++)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket > 0)
      {
         long dealMagic  = HistoryDealGetInteger(dealTicket, DEAL_MAGIC);
         long dealEntry  = HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
         string dealSym  = HistoryDealGetString(dealTicket, DEAL_SYMBOL);
         if(dealMagic == InpMagicNumber && dealSym == _Symbol && dealEntry == DEAL_ENTRY_IN)
            count++;
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Check if open position exists                                    |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(m_position.Magic() == InpMagicNumber && m_position.Symbol() == _Symbol)
            return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Draw visual range box & levels                                   |
//+------------------------------------------------------------------+
void UpdateChartBox(datetime tStart, datetime tEnd, double hPrice, double lPrice)
{
   if(!InpDrawBox) return;

   string boxName = "SWEEP_EA_Box";
   if(ObjectFind(0, boxName) < 0)
   {
      ObjectCreate(0, boxName, OBJ_RECTANGLE, 0, tStart, hPrice, tEnd, lPrice);
      ObjectSetInteger(0, boxName, OBJPROP_COLOR, InpBoxColor);
      ObjectSetInteger(0, boxName, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, boxName, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, boxName, OBJPROP_FILL, true);
      ObjectSetInteger(0, boxName, OBJPROP_BACK, true);
      ObjectSetInteger(0, boxName, OBJPROP_SELECTABLE, false);
   }
   else
   {
      ObjectSetInteger(0, boxName, OBJPROP_TIME, 0, tStart);
      ObjectSetDouble(0, boxName, OBJPROP_PRICE, 0, hPrice);
      ObjectSetInteger(0, boxName, OBJPROP_TIME, 1, tEnd);
      ObjectSetDouble(0, boxName, OBJPROP_PRICE, 1, lPrice);
   }

   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Dynamic Profit Lock Engine                                       |
//+------------------------------------------------------------------+
void ManageOpenPositionProfitLock()
{
   if(InpProfitLockType == LOCK_DISABLED) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!m_position.SelectByIndex(i)) continue;
      if(m_position.Magic() != InpMagicNumber || m_position.Symbol() != _Symbol) continue;

      ulong  posTicket  = m_position.Ticket();
      double openPrice  = m_position.PriceOpen();
      double currentSL  = m_position.StopLoss();
      double currentTP  = m_position.TakeProfit();
      ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)m_position.PositionType();
      double point      = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      int    digits     = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      long   stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);

      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      // Determine initial risk distance
      double initialRiskPrice = 0.0;
      if(posTicket == m_trackedTicket && m_trackedInitialRisk > 0.0)
      {
         initialRiskPrice = m_trackedInitialRisk;
      }
      else
      {
         if(currentSL > 0.0)
            initialRiskPrice = MathAbs(openPrice - currentSL);
         else
            initialRiskPrice = 200 * point;
      }

      if(initialRiskPrice <= 0.0) continue;

      // 1. Target-Progress Lock (Lock when reaching X% of TP distance)
      if(InpProfitLockType == LOCK_AT_TP_PERCENT)
      {
         if(currentTP <= 0.0) continue;

         double totalTPDist = 0.0;
         double currentGain = 0.0;

         if(posType == POSITION_TYPE_BUY)
         {
            totalTPDist = currentTP - openPrice;
            currentGain = bid - openPrice;
         }
         else // SELL
         {
            totalTPDist = openPrice - currentTP;
            currentGain = openPrice - ask;
         }

         if(totalTPDist <= 0.0) continue;

         double progressPct = (currentGain / totalTPDist) * 100.0;

         if(progressPct >= InpLockTriggerPct)
         {
            double desiredSL = 0.0;
            if(InpLockLevel == LOCK_TO_BREAK_EVEN)
            {
               desiredSL = openPrice;
            }
            else if(InpLockLevel == LOCK_TO_PLUS_HALF_R)
            {
               desiredSL = (posType == POSITION_TYPE_BUY) ? (openPrice + 0.5 * initialRiskPrice) : (openPrice - 0.5 * initialRiskPrice);
            }
            else if(InpLockLevel == LOCK_TO_PLUS_ONE_R)
            {
               desiredSL = (posType == POSITION_TYPE_BUY) ? (openPrice + 1.0 * initialRiskPrice) : (openPrice - 1.0 * initialRiskPrice);
            }
            else if(InpLockLevel == LOCK_HALF_WAY)
            {
               desiredSL = (posType == POSITION_TYPE_BUY) ? (openPrice + 0.5 * currentGain) : (openPrice - 0.5 * currentGain);
            }

            desiredSL = NormalizeDouble(desiredSL, digits);

            bool shouldModify = false;
            if(posType == POSITION_TYPE_BUY)
            {
               if((currentSL <= 0.0 || desiredSL > currentSL + point) && (bid - desiredSL > stopsLevel * point))
                  shouldModify = true;
            }
            else // SELL
            {
               if((currentSL <= 0.0 || desiredSL < currentSL - point) && (desiredSL - ask > stopsLevel * point))
                  shouldModify = true;
            }

            if(shouldModify)
            {
               PrintFormat("[PROFIT LOCK] Triggered! Progress: %.1f%% of TP. Modifying SL to %.2f", progressPct, desiredSL);
               if(m_trade.PositionModify(posTicket, desiredSL, currentTP))
               {
                  PrintFormat("[PROFIT LOCK] Ticket #%I64u SL updated successfully to %.2f", posTicket, desiredSL);
               }
            }
         }
      }
      // 2. Fixed R-Multiple Trigger (e.g. +2.0R -> lock +0.5R or BE)
      else if(InpProfitLockType == LOCK_AT_R_MULTIPLE)
      {
         double currentGain = (posType == POSITION_TYPE_BUY) ? (bid - openPrice) : (openPrice - ask);
         double currentR = currentGain / initialRiskPrice;

         if(currentR >= InpLockTriggerR)
         {
            double desiredSL = 0.0;
            if(InpLockLevel == LOCK_TO_BREAK_EVEN)
               desiredSL = openPrice;
            else if(InpLockLevel == LOCK_TO_PLUS_HALF_R)
               desiredSL = (posType == POSITION_TYPE_BUY) ? (openPrice + 0.5 * initialRiskPrice) : (openPrice - 0.5 * initialRiskPrice);
            else if(InpLockLevel == LOCK_TO_PLUS_ONE_R)
               desiredSL = (posType == POSITION_TYPE_BUY) ? (openPrice + 1.0 * initialRiskPrice) : (openPrice - 1.0 * initialRiskPrice);
            else
               desiredSL = (posType == POSITION_TYPE_BUY) ? (openPrice + (InpLockProfitFixedR * initialRiskPrice)) : (openPrice - (InpLockProfitFixedR * initialRiskPrice));

            desiredSL = NormalizeDouble(desiredSL, digits);

            bool shouldModify = false;
            if(posType == POSITION_TYPE_BUY)
            {
               if((currentSL <= 0.0 || desiredSL > currentSL + point) && (bid - desiredSL > stopsLevel * point))
                  shouldModify = true;
            }
            else
            {
               if((currentSL <= 0.0 || desiredSL < currentSL - point) && (desiredSL - ask > stopsLevel * point))
                  shouldModify = true;
            }

            if(shouldModify)
            {
               PrintFormat("[PROFIT LOCK R] Triggered at %.2f R! Modifying SL to %.2f", currentR, desiredSL);
               m_trade.PositionModify(posTicket, desiredSL, currentTP);
            }
         }
      }
      // 3. Stepped Trailing Stop
      else if(InpProfitLockType == LOCK_TRAILING_STEP)
      {
         double currentGain = (posType == POSITION_TYPE_BUY) ? (bid - openPrice) : (openPrice - ask);
         double currentR = currentGain / initialRiskPrice;

         double stepLockR = -1.0;
         if(currentR >= 3.5) stepLockR = 2.0;
         else if(currentR >= 2.5) stepLockR = 1.0;
         else if(currentR >= 1.5) stepLockR = 0.0;

         if(stepLockR >= 0.0)
         {
            double desiredSL = (posType == POSITION_TYPE_BUY) ? (openPrice + stepLockR * initialRiskPrice) : (openPrice - stepLockR * initialRiskPrice);
            desiredSL = NormalizeDouble(desiredSL, digits);

            bool shouldModify = false;
            if(posType == POSITION_TYPE_BUY)
            {
               if((currentSL <= 0.0 || desiredSL > currentSL + point) && (bid - desiredSL > stopsLevel * point))
                  shouldModify = true;
            }
            else
            {
               if((currentSL <= 0.0 || desiredSL < currentSL - point) && (desiredSL - ask > stopsLevel * point))
                  shouldModify = true;
            }

            if(shouldModify)
            {
               PrintFormat("[TRAILING STEP] Step %.1fR triggered! Modifying SL to %.2f", stepLockR, desiredSL);
               m_trade.PositionModify(posTicket, desiredSL, currentTP);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Manage open position profit locks on every tick
   ManageOpenPositionProfitLock();

   datetime currentBarTime = iTime(_Symbol, _Period, 0);
   bool isNewBar = (currentBarTime != m_lastBarTime);
   if(isNewBar)
   {
      m_lastBarTime = currentBarTime;
   }

   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);

   datetime dayStart = now - (dt.hour * 3600 + dt.min * 60 + dt.sec);
   int secNow = dt.hour * 3600 + dt.min * 60 + dt.sec;

   int rangeStartSec = TimeToSecondsOfDay(InpRangeStartTime);
   int rangeEndSec   = TimeToSecondsOfDay(InpRangeEndTime);
   int tradeStartSec = TimeToSecondsOfDay(InpTradeStartTime);
   int tradeEndSec   = TimeToSecondsOfDay(InpTradeEndTime);

   // 1. Calculate & establish the London Range Box strictly up to rangeEndSec
   if(secNow >= rangeEndSec)
   {
      datetime dtRangeStart = dayStart + rangeStartSec;
      datetime dtRangeEnd   = dayStart + rangeEndSec;

      int barStartIdx = iBarShift(_Symbol, _Period, dtRangeStart, false);
      int barEndIdx   = iBarShift(_Symbol, _Period, dtRangeEnd, false);

      if(barStartIdx >= 0 && barEndIdx >= 0 && barStartIdx >= barEndIdx)
      {
         int count = barStartIdx - barEndIdx + 1;
         int highestBar = iHighest(_Symbol, _Period, MODE_HIGH, count, barEndIdx);
         int lowestBar  = iLowest(_Symbol, _Period, MODE_LOW, count, barEndIdx);

         if(highestBar >= 0 && lowestBar >= 0)
         {
            m_rangeHigh = iHigh(_Symbol, _Period, highestBar);
            m_rangeLow  = iLow(_Symbol, _Period, lowestBar);
            m_rangeMid  = (m_rangeHigh + m_rangeLow) / 2.0;
            m_rangeFormed = (m_rangeHigh > m_rangeLow);

            UpdateChartBox(dtRangeStart, dtRangeEnd, m_rangeHigh, m_rangeLow);
         }
      }
   }

   m_tradesTodayCount = CountTradesToday(dayStart);

   // News Filter Checks
   bool isNFP = IsNFPFriday(now);
   bool isDateBlocked = IsDateBlacklisted(now, InpSkipDatesList);
   string detectedNewsName = "";
   bool isNewsNear = IsHighImpactUSDNewsNear(InpNewsBufferMins, detectedNewsName);

   if(m_manualNewsPause)
      m_newsStatusText = "PAUSED (Manual Button)";
   else if(isNFP)
      m_newsStatusText = "BLOCKED (NFP Jobs Friday)";
   else if(isDateBlocked)
      m_newsStatusText = "BLOCKED (Date Blacklisted)";
   else if(isNewsNear)
      m_newsStatusText = StringFormat("BLOCKED (%s)", detectedNewsName);
   else
      m_newsStatusText = "CLEAR (Trading Allowed)";

   // Live Status Dashboard
   string statusText = StringFormat(
      "--- LONDON SWEEP & NY REVERSAL EA (%s) v2.20 ---\n"
      "Broker Time: %02d:%02d:%02d | Window: %s - %s\n"
      "London Range: High=%.2f, Low=%.2f, Mid=%.2f (Size: %.1f pts)\n"
      "Trades Today: %d / %d | Open Position: %s | Profit Lock: %s\n"
      "News Shield: %s\n",
      _Symbol,
      dt.hour, dt.min, dt.sec,
      InpTradeStartTime, InpTradeEndTime,
      m_rangeHigh, m_rangeLow, m_rangeMid, (m_rangeHigh - m_rangeLow) / _Point,
      m_tradesTodayCount, InpMaxTradesPerDay,
      HasOpenPosition() ? "YES" : "NO",
      (InpProfitLockType == LOCK_DISABLED) ? "OFF" : "ACTIVE",
      m_newsStatusText
   );
   Comment(statusText);

   // 2. Sweep & Reversal Execution (Evaluated on Bar Close during NY Window)
   if(!isNewBar) return;
   if(secNow < tradeStartSec || secNow > tradeEndSec) return;
   if(!m_rangeFormed) return;
   if(m_tradesTodayCount >= InpMaxTradesPerDay) return;
   if(HasOpenPosition()) return;

   // News Shield Check: Do NOT open new trades if blocked by news
   if(m_manualNewsPause || isNFP || isDateBlocked || isNewsNear)
   {
      PrintFormat("[NEWS SHIELD ACTIVE] Trade skipped today: %s", m_newsStatusText);
      return;
   }

   // Spread filter
   long currentSpread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(InpMaxSpreadPoints > 0 && currentSpread > InpMaxSpreadPoints)
   {
      PrintFormat("[SPREAD GUARD] Current spread (%d pts) exceeds max allowed (%d pts). Trade skipped.", currentSpread, InpMaxSpreadPoints);
      return;
   }

   // Read bar 1 (just closed candle)
   double close1 = iClose(_Symbol, _Period, 1);
   double open1  = iOpen(_Symbol, _Period, 1);
   double high1  = iHigh(_Symbol, _Period, 1);
   double low1   = iLow(_Symbol, _Period, 1);

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   // --- A. BEARISH LIQUIDITY SWEEP (High Swept -> Reversal Sell) ---
   if(high1 > m_rangeHigh && close1 < m_rangeHigh)
   {
      double sweepDepth = (high1 - m_rangeHigh) / point;
      bool depthOk = (sweepDepth >= InpMinSweepPoints && sweepDepth <= InpMaxSweepPoints);
      bool dispOk  = !InpRequireDispCandle || (close1 < open1);

      if(depthOk && dispOk)
      {
         double slPrice = high1 + (InpSLBufferPoints * point);
         double slDist  = slPrice - bid;

         if(slDist > 0)
         {
            double tpPrice = 0.0;
            if(InpTargetMode == TP_RANGE_MIDPOINT)
               tpPrice = m_rangeMid;
            else if(InpTargetMode == TP_FIXED_RR_2_0)
               tpPrice = bid - (slDist * 2.0);
            else if(InpTargetMode == TP_FIXED_RR_2_5)
               tpPrice = bid - (slDist * 2.5);
            else // TP_OPPOSITE_RANGE
               tpPrice = m_rangeLow;

            if(bid > tpPrice)
            {
               slPrice = NormalizeDouble(slPrice, digits);
               tpPrice = NormalizeDouble(tpPrice, digits);

               double lotSize = CalculateLotSize(slDist);
               PrintFormat("[SWEEP SELL] Executing: Bid=%.2f, SL=%.2f, TP=%.2f, Lot=%.2f", bid, slPrice, tpPrice, lotSize);

               if(m_trade.Sell(lotSize, _Symbol, bid, slPrice, tpPrice, InpTradeComment))
               {
                  m_trackedTicket = m_trade.ResultOrder();
                  m_trackedInitialRisk = slDist;
                  Print("SWEEP SELL Placed Successfully! Ticket: ", m_trackedTicket);
               }
            }
         }
      }
   }
   // --- B. BULLISH LIQUIDITY SWEEP (Low Swept -> Reversal Buy) ---
   else if(low1 < m_rangeLow && close1 > m_rangeLow)
   {
      double sweepDepth = (m_rangeLow - low1) / point;
      bool depthOk = (sweepDepth >= InpMinSweepPoints && sweepDepth <= InpMaxSweepPoints);
      bool dispOk  = !InpRequireDispCandle || (close1 > open1);

      if(depthOk && dispOk)
      {
         double slPrice = low1 - (InpSLBufferPoints * point);
         double slDist  = ask - slPrice;

         if(slDist > 0)
         {
            double tpPrice = 0.0;
            if(InpTargetMode == TP_RANGE_MIDPOINT)
               tpPrice = m_rangeMid;
            else if(InpTargetMode == TP_FIXED_RR_2_0)
               tpPrice = ask + (slDist * 2.0);
            else if(InpTargetMode == TP_FIXED_RR_2_5)
               tpPrice = ask + (slDist * 2.5);
            else // TP_OPPOSITE_RANGE
               tpPrice = m_rangeHigh;

            if(tpPrice > ask)
            {
               slPrice = NormalizeDouble(slPrice, digits);
               tpPrice = NormalizeDouble(tpPrice, digits);

               double lotSize = CalculateLotSize(slDist);
               PrintFormat("[SWEEP BUY] Executing: Ask=%.2f, SL=%.2f, TP=%.2f, Lot=%.2f", ask, slPrice, tpPrice, lotSize);

               if(m_trade.Buy(lotSize, _Symbol, ask, slPrice, tpPrice, InpTradeComment))
               {
                  m_trackedTicket = m_trade.ResultOrder();
                  m_trackedInitialRisk = slDist;
                  Print("SWEEP BUY Placed Successfully! Ticket: ", m_trackedTicket);
               }
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
