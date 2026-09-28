//+------------------------------------------------------------------+
//|                                     H1_OrderBlock_Swing_EA.mq5  |
//|                                   Copyright 2026, Dineshfx / AI |
//|              Institutional H1 Order Block & Swing Strategy EA    |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Dineshfx"
#property link      "https://github.com/dinesh0293/Dineshfx"
#property version   "1.00"
#property description "Automated Institutional H1 Order Block Swing Strategy for Gold (XAUUSD) with 50% Partial Profit Booking."

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//--- Inputs
input group "=== Swing & Order Block Detection ==="
input ENUM_TIMEFRAMES InpStrategyTimeframe   = PERIOD_H1;      // Strategy Execution Timeframe (Locked to H1)
input int    InpPivotSpan             = 8;              // Swing Pivot Span (bars)
input int    InpMinDisplacementPoints = 800;            // Min Displacement ($8.00 = 800 pts on Gold)
input bool   InpRequireDailyTrend     = true;           // Filter by Daily 50 EMA Trend
input int    InpDailyEMAPeriod        = 50;             // Daily EMA Period
input int    InpSLBufferPoints        = 200;            // SL Buffer beyond swing wick ($2.00 = 200 pts)

input group "=== Targets & Money Management ==="
input double InpTargetRR              = 4.0;            // Final Target Risk-to-Reward (1:4.0 R:R)
input bool   InpEnablePartialTP       = true;           // Enable 50% Partial Close at +2.0R
input double InpPartialTriggerR       = 2.0;            // Partial Close Trigger R (+2.0R)
input double InpFixedLotSize          = 0.01;           // Fixed Lot Size (0.01 for $100 account)
input double InpRiskPercent           = 1.0;            // Risk Percent (used if Fixed Lot is 0.0)
input int    InpMaxOpenTrades         = 1;              // Max Concurrent Swing Trades
input ulong  InpMagicNumber           = 5502026;        // Magic Number
input string InpTradeComment          = "H1_OB_SWING";  // Trade Comment

input group "=== Visuals ==="
input bool   InpDrawBoxes             = false;           // Draw Order Block Rectangles
input color  InpColorBearishOB        = clrYellow;      // Bearish Order Block Color (The Yellow Box)
input color  InpColorBullishOB        = clrMediumSeaGreen; // Bullish Order Block Color

//--- Global Variables
CTrade         m_trade;
CPositionInfo  m_position;
datetime       m_lastBarTime = 0;
int            m_dailyEmaHandle = INVALID_HANDLE;

struct SOrderBlock
{
   bool     active;
   string   type;      // "BEARISH" or "BULLISH"
   datetime time;
   double   top;
   double   bottom;
   double   sl;
};

SOrderBlock m_activeOBs[];

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();
   m_trade.SetTypeFillingBySymbol(_Symbol);

   if(InpRequireDailyTrend)
   {
      m_dailyEmaHandle = iMA(_Symbol, PERIOD_D1, InpDailyEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   }

   Print("H1_OrderBlock_Swing_EA initialized on ", _Symbol, " Period: ", EnumToString(Period()));
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "H1_EA_OB_");
   Comment("");
   if(m_dailyEmaHandle != INVALID_HANDLE)
      IndicatorRelease(m_dailyEmaHandle);
}

//+------------------------------------------------------------------+
//| Draw visual range box                                            |
//+------------------------------------------------------------------+
void DrawOBBox(string name, datetime tStart, datetime tEnd, double top, double bottom, color clr)
{
   if(!InpDrawBoxes) return;

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, tStart, top, tEnd, bottom);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, name, OBJPROP_FILL, false);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
   else
   {
      ObjectSetInteger(0, name, OBJPROP_TIME, 1, tEnd);
   }
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Calculate Lot Size                                               |
//+------------------------------------------------------------------+
double GetLotSize(double slDistancePrice)
{
   if(InpFixedLotSize > 0.0) return InpFixedLotSize;

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
//| Count active open trades with our magic number                   |
//+------------------------------------------------------------------+
int CountOpenPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(m_position.Magic() == InpMagicNumber && m_position.Symbol() == _Symbol)
            count++;
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Manage Active Open Swing Positions (50% Partial Close & BE)      |
//+------------------------------------------------------------------+
void ManageOpenSwingTrades()
{
   if(!InpEnablePartialTP) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!m_position.SelectByIndex(i)) continue;
      if(m_position.Magic() != InpMagicNumber || m_position.Symbol() != _Symbol) continue;

      ulong  posTicket  = m_position.Ticket();
      double openPrice  = m_position.PriceOpen();
      double currentSL  = m_position.StopLoss();
      double currentTP  = m_position.TakeProfit();
      double posVolume  = m_position.Volume();
      ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)m_position.PositionType();
      int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      double initialRiskPrice = MathAbs(openPrice - currentSL);
      if(initialRiskPrice <= 0.0) continue;

      double currentGain = (posType == POSITION_TYPE_BUY) ? (bid - openPrice) : (openPrice - ask);
      double currentR = currentGain / initialRiskPrice;

      // Check +2.0R Trigger: Partial Close & Move SL to Break-Even
      if(currentR >= InpPartialTriggerR)
      {
         // 1. Move SL to Break-Even if not already done
         double bePrice = NormalizeDouble(openPrice, digits);
         bool shouldModifySL = false;

         if(posType == POSITION_TYPE_BUY && currentSL < openPrice)
            shouldModifySL = true;
         else if(posType == POSITION_TYPE_SELL && currentSL > openPrice)
            shouldModifySL = true;

         if(shouldModifySL)
         {
            PrintFormat("[H1 SWING] +%.1fR reached! Moving SL to Break-Even (%.2f)", currentR, bePrice);
            m_trade.PositionModify(posTicket, bePrice, currentTP);
         }

         // 2. Close 50% partial volume if volume > min lot
         double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         if(posVolume > lotMin)
         {
            double closeVolume = posVolume / 2.0;
            double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
            closeVolume = MathFloor(closeVolume / lotStep) * lotStep;

            if(closeVolume >= lotMin)
            {
               PrintFormat("[H1 SWING] 50%% PROFIT BOOKED! Closing %.2f lots of ticket #%I64u", closeVolume, posTicket);
               m_trade.PositionClosePartial(posTicket, closeVolume);
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
   ManageOpenSwingTrades();

   datetime currentBarTime = iTime(_Symbol, InpStrategyTimeframe, 0);
   bool isNewBar = (currentBarTime != m_lastBarTime);
   if(isNewBar)
   {
      m_lastBarTime = currentBarTime;
   }

   // Status Dashboard
   int openCount = CountOpenPositions();
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   string status = StringFormat(
      "--- H1 ORDER BLOCK SWING TRADER (%s) ---\n"
      "Timeframe: %s | Open Positions: %d / %d\n"
      "Strategy: Daily Trend + H1 Liquidity Sweep + OB Retest\n"
      "Target: 1:%.1f R:R (50%% Partial at +%.1fR)\n"
      "Lot Sizing: %.2f Fixed Lot\n",
      _Symbol,
      EnumToString(Period()),
      openCount, InpMaxOpenTrades,
      InpTargetRR, InpPartialTriggerR,
      InpFixedLotSize
   );
   Comment(status);

   if(!isNewBar) return;

   // Detect new Order Blocks on H1 close
   int barsTotal = iBars(_Symbol, _Period);
   if(barsTotal < InpPivotSpan * 4) return;

   // Check Daily EMA Trend
   double dailyEma[1];
   bool dailyTrendUp = true;
   bool dailyTrendDown = true;
   if(InpRequireDailyTrend && m_dailyEmaHandle != INVALID_HANDLE)
   {
      if(CopyBuffer(m_dailyEmaHandle, 0, 0, 1, dailyEma) > 0)
      {
         double lastDClose = iClose(_Symbol, PERIOD_D1, 1);
         dailyTrendUp   = (lastDClose > dailyEma[0]);
         dailyTrendDown = (lastDClose < dailyEma[0]);
      }
   }

   // Check if a swing high occurred at bar InpPivotSpan
   int checkIdx = InpPivotSpan;
   double checkHigh = iHigh(_Symbol, InpStrategyTimeframe, checkIdx);
   bool isSwingHigh = true;

   for(int k = 1; k <= InpPivotSpan; k++)
   {
      if(iHigh(_Symbol, InpStrategyTimeframe, checkIdx - k) >= checkHigh || iHigh(_Symbol, InpStrategyTimeframe, checkIdx + k) >= checkHigh)
      {
         isSwingHigh = false;
         break;
      }
   }

   double minDisp = InpMinDisplacementPoints * point;

   if(isSwingHigh && dailyTrendDown)
   {
      double dropLow = iLow(_Symbol, InpStrategyTimeframe, checkIdx - 1);
      for(int d = 2; d <= 4; d++)
      {
         if(checkIdx - d >= 0 && iLow(_Symbol, InpStrategyTimeframe, checkIdx - d) < dropLow)
            dropLow = iLow(_Symbol, InpStrategyTimeframe, checkIdx - d);
      }

      if((checkHigh - dropLow) >= minDisp)
      {
         int sz = ArraySize(m_activeOBs);
         ArrayResize(m_activeOBs, sz + 1);
         m_activeOBs[sz].active = true;
         m_activeOBs[sz].type = "BEARISH";
         m_activeOBs[sz].time = iTime(_Symbol, InpStrategyTimeframe, checkIdx);
         m_activeOBs[sz].top = checkHigh;
         m_activeOBs[sz].bottom = MathMin(iOpen(_Symbol, InpStrategyTimeframe, checkIdx), iClose(_Symbol, InpStrategyTimeframe, checkIdx));
         m_activeOBs[sz].sl = checkHigh + (InpSLBufferPoints * point);

         string obName = StringFormat("H1_EA_OB_SELL_%s", TimeToString(m_activeOBs[sz].time, TIME_DATE|TIME_MINUTES));
         DrawOBBox(obName, m_activeOBs[sz].time, currentBarTime + (PeriodSeconds(InpStrategyTimeframe) * 24), m_activeOBs[sz].top, m_activeOBs[sz].bottom, InpColorBearishOB);
         Print("[H1 SWING] New Bearish Order Block detected: ", obName);
      }
   }

   // Check if a swing low occurred at bar InpPivotSpan
   double checkLow = iLow(_Symbol, InpStrategyTimeframe, checkIdx);
   bool isSwingLow = true;

   for(int k = 1; k <= InpPivotSpan; k++)
   {
      if(iLow(_Symbol, InpStrategyTimeframe, checkIdx - k) <= checkLow || iLow(_Symbol, InpStrategyTimeframe, checkIdx + k) <= checkLow)
      {
         isSwingLow = false;
         break;
      }
   }

   if(isSwingLow && dailyTrendUp)
   {
      double rallyHigh = iHigh(_Symbol, InpStrategyTimeframe, checkIdx - 1);
      for(int d = 2; d <= 4; d++)
      {
         if(checkIdx - d >= 0 && iHigh(_Symbol, InpStrategyTimeframe, checkIdx - d) > rallyHigh)
            rallyHigh = iHigh(_Symbol, InpStrategyTimeframe, checkIdx - d);
      }

      if((rallyHigh - checkLow) >= minDisp)
      {
         int sz = ArraySize(m_activeOBs);
         ArrayResize(m_activeOBs, sz + 1);
         m_activeOBs[sz].active = true;
         m_activeOBs[sz].type = "BULLISH";
         m_activeOBs[sz].time = iTime(_Symbol, InpStrategyTimeframe, checkIdx);
         m_activeOBs[sz].top = MathMax(iOpen(_Symbol, InpStrategyTimeframe, checkIdx), iClose(_Symbol, InpStrategyTimeframe, checkIdx));
         m_activeOBs[sz].bottom = checkLow;
         m_activeOBs[sz].sl = checkLow - (InpSLBufferPoints * point);

         string obName = StringFormat("H1_EA_OB_BUY_%s", TimeToString(m_activeOBs[sz].time, TIME_DATE|TIME_MINUTES));
         DrawOBBox(obName, m_activeOBs[sz].time, currentBarTime + (PeriodSeconds(InpStrategyTimeframe) * 24), m_activeOBs[sz].top, m_activeOBs[sz].bottom, InpColorBullishOB);
         Print("[H1 SWING] New Bullish Order Block detected: ", obName);
      }
   }

   // Execution: Check for retests of unmitigated Order Blocks
   if(openCount >= InpMaxOpenTrades) return;

   double high1 = iHigh(_Symbol, InpStrategyTimeframe, 1);
   double low1  = iLow(_Symbol, InpStrategyTimeframe, 1);

   for(int i = ArraySize(m_activeOBs) - 1; i >= 0; i--)
   {
      if(!m_activeOBs[i].active) continue;

      if(m_activeOBs[i].type == "BEARISH")
      {
         if(high1 >= m_activeOBs[i].bottom && high1 <= (m_activeOBs[i].top + 100 * point))
         {
            double slPrice = NormalizeDouble(m_activeOBs[i].sl, digits);
            double slDist  = slPrice - bid;

            if(slDist > 0)
            {
               double tpPrice = NormalizeDouble(bid - (slDist * InpTargetRR), digits);
               double lotSize = GetLotSize(slDist);

               PrintFormat("[SWING SELL ENTRY] Executing: Bid=%.2f, SL=%.2f, TP=%.2f, Lot=%.2f", bid, slPrice, tpPrice, lotSize);
               if(m_trade.Sell(lotSize, _Symbol, bid, slPrice, tpPrice, InpTradeComment))
               {
                  Print("SWING SELL Placed! Order: ", m_trade.ResultOrder());
                  m_activeOBs[i].active = false;
                  break;
               }
            }
         }
      }
      else if(m_activeOBs[i].type == "BULLISH")
      {
         if(low1 <= m_activeOBs[i].top && low1 >= (m_activeOBs[i].bottom - 100 * point))
         {
            double slPrice = NormalizeDouble(m_activeOBs[i].sl, digits);
            double slDist  = ask - slPrice;

            if(slDist > 0)
            {
               double tpPrice = NormalizeDouble(ask + (slDist * InpTargetRR), digits);
               double lotSize = GetLotSize(slDist);

               PrintFormat("[SWING BUY ENTRY] Executing: Ask=%.2f, SL=%.2f, TP=%.2f, Lot=%.2f", ask, slPrice, tpPrice, lotSize);
               if(m_trade.Buy(lotSize, _Symbol, ask, slPrice, tpPrice, InpTradeComment))
               {
                  Print("SWING BUY Placed! Order: ", m_trade.ResultOrder());
                  m_activeOBs[i].active = false;
                  break;
               }
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
