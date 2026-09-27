//+------------------------------------------------------------------+
//|                                  London_Sweep_NY_Reversal_EA.mq5 |
//|                                   Copyright 2026, Dineshfx / AI |
//|                London Liquidity Sweep & NY Reversal Strategy     |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Dineshfx"
#property link      "https://github.com/dinesh0293/Dineshfx"
#property version   "2.00"
#property description "Institutional Liquidity Sweep & Mean Reversion Strategy for Gold (XAUUSD)."

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//--- Enums
enum ENUM_TP_MODE
{
   TP_RANGE_MIDPOINT = 0, // 50% Range Midpoint (Proven +70.9R)
   TP_FIXED_RR_2_0   = 1, // Fixed 1:2.0 Risk-to-Reward
   TP_FIXED_RR_2_5   = 2, // Fixed 1:2.5 Risk-to-Reward
   TP_OPPOSITE_RANGE = 3  // Opposite London Session Extreme
};

//--- Inputs
input group "=== Session Times (Broker Server Time - Vantage GMT+3) ==="
input string         InpRangeStartTime    = "11:00";    // London Core Range Start (04:00 AM NY)
input string         InpRangeEndTime      = "15:55";    // Freeze 5 min before NY (08:55 AM NY)
input string         InpTradeStartTime    = "16:00";    // NY Sweep Window Start (09:00 AM NY)
input string         InpTradeEndTime      = "18:30";    // NY Sweep Window End (11:30 AM NY)

input group "=== Sweep Confirmation & Filters ==="
input int            InpMinSweepPoints    = 30;         // Min Sweep Depth ($0.30 on Gold = 30 pts)
input int            InpMaxSweepPoints    = 500;        // Max Sweep Depth ($5.00 on Gold = 500 pts)
input bool           InpRequireDispCandle = true;       // Require Reversal Candle (Close < Open for Sell, Close > Open for Buy)
input int            InpSLBufferPoints    = 50;         // SL Buffer beyond sweep wick ($0.50 = 50 pts)
input ENUM_TP_MODE   InpTargetMode        = TP_RANGE_MIDPOINT; // Take Profit Mode

input group "=== Risk & Money Management ==="
input double         InpRiskPercent       = 1.0;        // Risk Percentage (% of Equity)
input double         InpFixedLotSize      = 0.0;        // Fixed Lot (0.0 = Use Risk Percent)
input int            InpMaxSpreadPoints   = 60;         // Max Allowed Spread (points)
input int            InpMaxTradesPerDay   = 1;          // Max trades per day
input ulong          InpMagicNumber       = 4402026;    // Magic Number
input string         InpTradeComment      = "SWEEP_REV"; // Trade Comment

input group "=== Visuals ==="
input bool           InpDrawBox           = true;       // Draw London Box on Chart
input color          InpBoxColor          = clrDodgerBlue; // Range Box Color

//--- Global Variables
CTrade         m_trade;
CPositionInfo  m_position;
datetime       m_lastBarTime = 0;
int            m_tradesTodayCount = 0;

double         m_rangeHigh = 0.0;
double         m_rangeLow  = 0.0;
double         m_rangeMid  = 0.0;
bool           m_rangeFormed = false;

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
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();
   m_trade.SetTypeFillingBySymbol(_Symbol);

   Print("London_Sweep_NY_Reversal_EA initialized on ", _Symbol, " Period: ", EnumToString(Period()));
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
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
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

   // Live Status Dashboard
   string statusText = StringFormat(
      "--- LONDON SWEEP & NY REVERSAL EA (%s) ---\n"
      "Broker Time: %02d:%02d:%02d | Window: %s - %s\n"
      "London Range: High=%.2f, Low=%.2f, Mid=%.2f (Size: %.1f pts)\n"
      "Trades Today: %d / %d | Open Position: %s\n",
      _Symbol,
      dt.hour, dt.min, dt.sec,
      InpTradeStartTime, InpTradeEndTime,
      m_rangeHigh, m_rangeLow, m_rangeMid, (m_rangeHigh - m_rangeLow) / _Point,
      m_tradesTodayCount, InpMaxTradesPerDay,
      HasOpenPosition() ? "YES" : "NO"
   );
   Comment(statusText);

   // 2. Sweep & Reversal Execution (Evaluated on Bar Close during NY Window)
   if(!isNewBar) return;
   if(secNow < tradeStartSec || secNow > tradeEndSec) return;
   if(!m_rangeFormed) return;
   if(m_tradesTodayCount >= InpMaxTradesPerDay) return;
   if(HasOpenPosition()) return;

   // Spread filter
   long currentSpread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(InpMaxSpreadPoints > 0 && currentSpread > InpMaxSpreadPoints) return;

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
      bool dispOk  = !InpRequireDispCandle || (close1 < open1); // Bearish candle

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
                  Print("SWEEP SELL Placed Successfully! Ticket: ", m_trade.ResultOrder());
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
      bool dispOk  = !InpRequireDispCandle || (close1 > open1); // Bullish candle

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
                  Print("SWEEP BUY Placed Successfully! Ticket: ", m_trade.ResultOrder());
               }
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
