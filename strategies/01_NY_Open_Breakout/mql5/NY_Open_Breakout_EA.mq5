//+------------------------------------------------------------------+
//|                                        NY_Open_Breakout_EA.mq5   |
//|                                  Copyright 2026, Antigravity AI |
//|              New York Open (9:30 AM EST) Breakout Expert Advisor |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Antigravity AI"
#property link      "https://metatrader5.com"
#property version   "1.00"
#property description "Automated Opening Range Breakout (ORB) Strategy for XAUUSD & Indices."

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//--- Enums
enum ENUM_SL_MODE
{
   SL_BREAKOUT_CANDLE = 0, // Below/Above Breakout Candle
   SL_BOX_MIDPOINT    = 1, // Range Box 50% Midpoint
   SL_BOX_OPPOSITE    = 2  // Opposite Side of Range Box
};

//--- Inputs
input group "=== Session Times (Broker Server Time) ==="
input string         InpRangeStartTime    = "15:00";    // Pre-Market Range Start (8:00 AM NY)
input string         InpRangeEndTime      = "16:25";    // Pre-Market Range End (9:25 AM NY)
input string         InpTradeStartTime    = "16:30";    // NY Open Bell (9:30 AM NY)
input string         InpTradeEndTime      = "17:15";    // End of Entry Window (10:15 AM NY)

input group "=== Risk & Money Management ==="
input double         InpRiskPercent       = 1.0;        // Risk Percentage per trade (% of Equity)
input double         InpFixedLotSize      = 0.0;        // Fixed Lot (0.0 = use Risk Percent)
input double         InpRiskRewardRatio   = 2.0;        // Risk to Reward Ratio (e.g. 2.0 for 1:2)
input ENUM_SL_MODE   InpStopLossMode      = SL_BREAKOUT_CANDLE; // Stop Loss Placement Mode
input int            InpSLBufferPoints    = 50;         // SL Buffer beyond candle/box (points)
input int            InpMaxSpreadPoints   = 60;         // Max Allowed Spread (points, 0 = disabled)
input int            InpMaxTradesPerDay   = 1;          // Max trades per day

input group "=== Trade Settings ==="
input ulong          InpMagicNumber       = 9302026;    // Magic Number
input string         InpTradeComment      = "NY_ORB";   // Trade Comment
input bool           InpCloseOpenAtEOD    = false;      // Auto-close open position at end of session
input string         InpEODCloseTime      = "23:00";    // End of Day Close Time (Broker Time)

input group "=== Visuals ==="
input bool           InpDrawBox           = true;       // Draw Range Box on Chart
input color          InpBoxColor          = clrDodgerBlue; // Range Box Color

//--- Global Variables
CTrade         m_trade;
CPositionInfo  m_position;
datetime       m_lastBarTime = 0;
datetime       m_lastTradeDay = 0;
int            m_tradesTodayCount = 0;

double         m_rangeHigh = 0.0;
double         m_rangeLow  = 0.0;
bool           m_rangeFormed = false;

//+------------------------------------------------------------------+
//| Helper: Convert "HH:MM" string to seconds from midnight          |
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

   Print("NY_Open_Breakout_EA initialized on ", _Symbol, " timeframe: ", EnumToString(Period()));
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "NYORB_EA_");
   Comment("");
}

//+------------------------------------------------------------------+
//| Calculate dynamic lot size based on Risk Percentage and SL       |
//+------------------------------------------------------------------+
double CalculateLotSize(double slDistancePrice)
{
   if(InpFixedLotSize > 0.0)
      return InpFixedLotSize;

   if(slDistancePrice <= 0.0)
      return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * (InpRiskPercent / 100.0);

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(tickSize <= 0.0 || tickValue <= 0.0 || point <= 0.0)
      return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

   // Points risk
   double pointsRisk = slDistancePrice / point;
   double moneyRiskPerLot = pointsRisk * (tickValue / (tickSize / point));

   if(moneyRiskPerLot <= 0.0)
      return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

   double calculatedLot = riskAmount / moneyRiskPerLot;

   // Align with broker lot step, min, and max
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   calculatedLot = MathFloor(calculatedLot / lotStep) * lotStep;
   if(calculatedLot < lotMin) calculatedLot = lotMin;
   if(calculatedLot > lotMax) calculatedLot = lotMax;

   return calculatedLot;
}

//+------------------------------------------------------------------+
//| Count trades executed today with our magic number                |
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
         long dealMagic = HistoryDealGetInteger(dealTicket, DEAL_MAGIC);
         long dealEntry = HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
         string dealSymbol = HistoryDealGetString(dealTicket, DEAL_SYMBOL);
         if(dealMagic == InpMagicNumber && dealSymbol == _Symbol && dealEntry == DEAL_ENTRY_IN)
         {
            count++;
         }
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Check if we currently have an open position                      |
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
//| Draw visual range box on chart                                   |
//+------------------------------------------------------------------+
void UpdateChartBox(datetime tStart, datetime tEnd, double hPrice, double lPrice)
{
   if(!InpDrawBox) return;

   string boxName = "NYORB_EA_Box";
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
   // Check bar arrival (execute breakout decisions on bar close)
   datetime currentBarTime = iTime(_Symbol, _Period, 0);
   bool isNewBar = (currentBarTime != m_lastBarTime);
   if(isNewBar)
   {
      m_lastBarTime = currentBarTime;
   }

   // Get current server time breakdown
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);

   datetime dayStart = now - (dt.hour * 3600 + dt.min * 60 + dt.sec);
   int secNow = dt.hour * 3600 + dt.min * 60 + dt.sec;

   int rangeStartSec = TimeToSecondsOfDay(InpRangeStartTime);
   int rangeEndSec   = TimeToSecondsOfDay(InpRangeEndTime);
   int tradeStartSec = TimeToSecondsOfDay(InpTradeStartTime);
   int tradeEndSec   = TimeToSecondsOfDay(InpTradeEndTime);
   int eodCloseSec   = TimeToSecondsOfDay(InpEODCloseTime);

   // Auto-close open position at EOD if enabled
   if(InpCloseOpenAtEOD && secNow >= eodCloseSec)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(m_position.SelectByIndex(i))
         {
            if(m_position.Magic() == InpMagicNumber && m_position.Symbol() == _Symbol)
               m_trade.PositionClose(m_position.Ticket());
         }
      }
   }

   // 1. Calculate & establish the Range Box during / up to rangeEndSec
   if(secNow >= rangeEndSec && secNow < tradeEndSec)
   {
      datetime dtRangeStart = dayStart + rangeStartSec;
      datetime dtRangeEnd   = dayStart + rangeEndSec;

      // Extract highest high and lowest low between dtRangeStart and dtRangeEnd
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
            m_rangeFormed = (m_rangeHigh > m_rangeLow);

            UpdateChartBox(dtRangeStart, dtRangeEnd, m_rangeHigh, m_rangeLow);
         }
      }
   }

   // Check today's trade count
   m_tradesTodayCount = CountTradesToday(dayStart);

   // On-chart Status Dashboard
   string statusText = StringFormat(
      "--- NY OPEN ORB EA (%s) ---\n"
      "Broker Time: %02d:%02d:%02d | Target Window: %s - %s\n"
      "Range Box: High=%.2f, Low=%.2f (Size: %.1f pts)\n"
      "Trades Taken Today: %d / %d | Open Position: %s\n",
      _Symbol,
      dt.hour, dt.min, dt.sec,
      InpTradeStartTime, InpTradeEndTime,
      m_rangeHigh, m_rangeLow, (m_rangeHigh - m_rangeLow) / _Point,
      m_tradesTodayCount, InpMaxTradesPerDay,
      HasOpenPosition() ? "YES" : "NO"
   );
   Comment(statusText);

   // 2. Breakout Evaluation & Trading Logic
   // Only evaluate on newly closed bars during the trade window
   if(!isNewBar) return;
   if(secNow < tradeStartSec || secNow > tradeEndSec) return;
   if(!m_rangeFormed) return;
   if(m_tradesTodayCount >= InpMaxTradesPerDay) return;
   if(HasOpenPosition()) return;

   // Spread check
   long currentSpread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(InpMaxSpreadPoints > 0 && currentSpread > InpMaxSpreadPoints)
   {
      Print("Spread too high (", currentSpread, " pts). Trade skipped.");
      return;
   }

   // Read bar 1 (the candle that just closed)
   double close1 = iClose(_Symbol, _Period, 1);
   double open1  = iOpen(_Symbol, _Period, 1);
   double high1  = iHigh(_Symbol, _Period, 1);
   double low1   = iLow(_Symbol, _Period, 1);

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   //--- BULLISH BREAKOUT
   if(close1 > m_rangeHigh)
   {
      double slPrice = 0.0;
      if(InpStopLossMode == SL_BREAKOUT_CANDLE)
         slPrice = low1 - (InpSLBufferPoints * point);
      else if(InpStopLossMode == SL_BOX_MIDPOINT)
         slPrice = (m_rangeHigh + m_rangeLow) / 2.0;
      else // SL_BOX_OPPOSITE
         slPrice = m_rangeLow - (InpSLBufferPoints * point);

      double slDist = ask - slPrice;
      if(slDist > 0)
      {
         double tpPrice = ask + (slDist * InpRiskRewardRatio);
         slPrice = NormalizeDouble(slPrice, digits);
         tpPrice = NormalizeDouble(tpPrice, digits);

         double lotSize = CalculateLotSize(slDist);
         PrintFormat("Executing BUY: Ask=%.2f, SL=%.2f, TP=%.2f, Lot=%.2f", ask, slPrice, tpPrice, lotSize);

         if(m_trade.Buy(lotSize, _Symbol, ask, slPrice, tpPrice, InpTradeComment))
         {
            Print("BUY Order Placed Successfully! Ticket: ", m_trade.ResultOrder());
         }
         else
         {
            Print("BUY Order Failed! Error: ", GetLastError(), " Retcode: ", m_trade.ResultRetcodeDescription());
         }
      }
   }
   //--- BEARISH BREAKOUT
   else if(close1 < m_rangeLow)

   {
      double slPrice = 0.0;
      if(InpStopLossMode == SL_BREAKOUT_CANDLE)
         slPrice = high1 + (InpSLBufferPoints * point);
      else if(InpStopLossMode == SL_BOX_MIDPOINT)
         slPrice = (m_rangeHigh + m_rangeLow) / 2.0;
      else // SL_BOX_OPPOSITE
         slPrice = m_rangeHigh + (InpSLBufferPoints * point);

      double slDist = slPrice - bid;
      if(slDist > 0)
      {
         double tpPrice = bid - (slDist * InpRiskRewardRatio);
         slPrice = NormalizeDouble(slPrice, digits);
         tpPrice = NormalizeDouble(tpPrice, digits);

         double lotSize = CalculateLotSize(slDist);
         PrintFormat("Executing SELL: Bid=%.2f, SL=%.2f, TP=%.2f, Lot=%.2f", bid, slPrice, tpPrice, lotSize);

         if(m_trade.Sell(lotSize, _Symbol, bid, slPrice, tpPrice, InpTradeComment))
         {
            Print("SELL Order Placed Successfully! Ticket: ", m_trade.ResultOrder());
         }
         else
         {
            Print("SELL Order Failed! Error: ", GetLastError(), " Retcode: ", m_trade.ResultRetcodeDescription());
         }
      }
   }
}
//+------------------------------------------------------------------+
