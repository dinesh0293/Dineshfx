//+------------------------------------------------------------------+
//|                                   H1_OrderBlock_Pyramid_EA.mq5  |
//|                                   Copyright 2026, Dineshfx / AI |
//|        Institutional H1 Order Block Swing Trader + Pyramiding    |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Dineshfx"
#property link      "https://github.com/dinesh0293/Dineshfx"
#property version   "2.00"
#property description "Institutional H1 Order Block Swing Strategy for Gold (XAUUSD) with Continuation OB Trailing and Risk-Free Pyramiding."

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

input group "=== Profit Locking & Pyramiding (Options 2 & 3) ==="
input bool   InpEnableContinuationTrailing = true;      // Option 2: Trail SL behind Continuation OBs
input bool   InpEnableRiskFreePyramid      = true;      // Option 3: Risk-Free Pyramiding (Add 2nd trade on continuation)
input double InpPyramidMinProfitR          = 2.0;       // Minimum R profit on Trade 1 before Pyramiding (+2.0R)
input int    InpMaxOpenTrades              = 2;         // Max Concurrent Trades (1 Base + 1 Pyramid)

input group "=== Targets & Money Management ==="
input double InpTargetRR              = 4.0;            // Final Target Risk-to-Reward (1:4.0 R:R)
input bool   InpEnablePartialTP       = true;           // Enable 50% Partial Close at +1.5R (if vol > min lot)
input double InpPartialTriggerR       = 1.5;            // Partial Close Trigger R (+1.5R)
input double InpFixedLotSize          = 0.01;           // Fixed Lot Size (0.01 for $100 account)
input double InpRiskPercent           = 1.0;            // Risk Percent (used if Fixed Lot is 0.0)
input ulong  InpMagicNumber           = 5502027;        // Magic Number for Pyramid EA
input string InpTradeComment          = "H1_OB_PYRAMID"; // Trade Comment

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
      if(m_dailyEmaHandle == INVALID_HANDLE)
      {
         Print("Failed to create Daily EMA handle! Error: ", GetLastError());
         return(INIT_FAILED);
      }
   }

   PrintFormat("H1_OrderBlock_Pyramid_EA initialized on %s (Locked TF: %s). FixedLot: %.2f, MaxTrades: %d",
               _Symbol, EnumToString(InpStrategyTimeframe), InpFixedLotSize, InpMaxOpenTrades);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Comment("");
   if(m_dailyEmaHandle != INVALID_HANDLE)
      IndicatorRelease(m_dailyEmaHandle);
}

//+------------------------------------------------------------------+
//| Count Open Positions by Magic Number                             |
//+------------------------------------------------------------------+
int CountOpenPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber)
            count++;
      }
   }
   return(count);
}

//+------------------------------------------------------------------+
//| Check if Base Trade is Risk-Free and Qualifies for Pyramiding   |
//+------------------------------------------------------------------+
bool IsBaseTradeRiskFree(double &firstTradeTP, ENUM_POSITION_TYPE &posType)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber)
         {
            posType = m_position.PositionType();
            double openPrice = m_position.PriceOpen();
            double currentSL = m_position.StopLoss();
            double currentPrice = m_position.PriceCurrent();
            firstTradeTP = m_position.TakeProfit();

            double initialRisk = MathAbs(openPrice - currentSL);
            if(initialRisk <= 0) continue;

            if(posType == POSITION_TYPE_SELL)
            {
               // Must be in profit by at least InpPyramidMinProfitR and SL at or below Break-Even
               double profitPts = openPrice - currentPrice;
               double currentR = profitPts / initialRisk;
               if(currentR >= InpPyramidMinProfitR && currentSL <= openPrice)
                  return(true);
            }
            else if(posType == POSITION_TYPE_BUY)
            {
               double profitPts = currentPrice - openPrice;
               double currentR = profitPts / initialRisk;
               if(currentR >= InpPyramidMinProfitR && currentSL >= openPrice)
                  return(true);
            }
         }
      }
   }
   return(false);
}

//+------------------------------------------------------------------+
//| Manage Open Trades (Break-Even + Continuation Structural Trailing)|
//+------------------------------------------------------------------+
void ManageOpenSwingTrades()
{
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(m_position.Symbol() != _Symbol || m_position.Magic() != InpMagicNumber)
            continue;

         ulong  posTicket    = m_position.Ticket();
         ENUM_POSITION_TYPE posType = m_position.PositionType();
         double openPrice    = m_position.PriceOpen();
         double currentPrice = m_position.PriceCurrent();
         double currentSL    = m_position.StopLoss();
         double currentTP    = m_position.TakeProfit();
         double posVolume    = m_position.Volume();

         double initialRisk = MathAbs(openPrice - currentSL);
         if(initialRisk <= 0) continue;

         double currentProfitPoints = 0.0;
         if(posType == POSITION_TYPE_BUY)
            currentProfitPoints = currentPrice - openPrice;
         else
            currentProfitPoints = openPrice - currentPrice;

         double currentR = currentProfitPoints / initialRisk;

         // 1. Move SL to Break-Even at +2.0R trigger
         if(currentR >= InpPartialTriggerR)
         {
            double bePrice = NormalizeDouble(openPrice, digits);
            bool shouldModifySL = false;

            if(posType == POSITION_TYPE_BUY && currentSL < openPrice)
               shouldModifySL = true;
            else if(posType == POSITION_TYPE_SELL && (currentSL > openPrice || currentSL == 0.0))
               shouldModifySL = true;

            if(shouldModifySL)
            {
               PrintFormat("[PYRAMID EA] +%.1fR reached! Securing ticket #%I64u to Break-Even (%.2f)", currentR, posTicket, bePrice);
               m_trade.PositionModify(posTicket, bePrice, currentTP);
               currentSL = bePrice;
            }

            // 50% partial close if volume allows
            double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
            if(InpEnablePartialTP && posVolume > lotMin)
            {
               double closeVolume = posVolume / 2.0;
               double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
               closeVolume = MathFloor(closeVolume / lotStep) * lotStep;

               if(closeVolume >= lotMin)
               {
                  PrintFormat("[PYRAMID EA] 50%% PROFIT BOOKED! Closing %.2f lots of ticket #%I64u", closeVolume, posTicket);
                  m_trade.PositionClosePartial(posTicket, closeVolume);
               }
            }
         }

         // 2. Option 2: Continuation OB Structural Trailing
         if(InpEnableContinuationTrailing && currentR >= 1.5)
         {
            // Check active order blocks for a tighter structural shield
            for(int ob = ArraySize(m_activeOBs) - 1; ob >= 0; ob--)
            {
               if(!m_activeOBs[ob].active) continue;

               if(posType == POSITION_TYPE_SELL && m_activeOBs[ob].type == "BEARISH")
               {
                  double obShieldSL = NormalizeDouble(m_activeOBs[ob].sl, digits);
                  // Only trail downwards (tighter)
                  if(obShieldSL < currentSL && obShieldSL < openPrice)
                  {
                     PrintFormat("[STRUCTURAL TRAIL] Trailing SELL #%I64u SL from %.2f -> %.2f behind Continuation OB",
                                 posTicket, currentSL, obShieldSL);
                     m_trade.PositionModify(posTicket, obShieldSL, currentTP);
                     currentSL = obShieldSL;
                     break;
                  }
               }
               else if(posType == POSITION_TYPE_BUY && m_activeOBs[ob].type == "BULLISH")
               {
                  double obShieldSL = NormalizeDouble(m_activeOBs[ob].sl, digits);
                  // Only trail upwards (tighter)
                  if(obShieldSL > currentSL && obShieldSL > openPrice)
                  {
                     PrintFormat("[STRUCTURAL TRAIL] Trailing BUY #%I64u SL from %.2f -> %.2f behind Continuation OB",
                                 posTicket, currentSL, obShieldSL);
                     m_trade.PositionModify(posTicket, obShieldSL, currentTP);
                     currentSL = obShieldSL;
                     break;
                  }
               }
            }
         }
      }
   }
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
   calculatedLot = MathFloor(calculatedLot / lotStep) * lotStep;

   double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   return MathMax(lotMin, MathMin(lotMax, calculatedLot));
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

   int openCount = CountOpenPositions();
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   // Status Dashboard
   string status = StringFormat(
      "=== H1 ORDER BLOCK PYRAMID EA (PRO) ===\n"
      "Timeframe: %s (Locked) | Open Positions: %d / %d\n"
      "Continuation Trailing (Opt 2): %s\n"
      "Risk-Free Pyramiding (Opt 3): %s\n"
      "Lot Sizing: %.2f Fixed Lot\n"
      "Account Equity: $%.2f | Margin Free: $%.2f",
      EnumToString(InpStrategyTimeframe), openCount, InpMaxOpenTrades,
      InpEnableContinuationTrailing ? "ACTIVE (Structural Shield)" : "OFF",
      InpEnableRiskFreePyramid ? "ENABLED (+2.0R Gate)" : "OFF",
      InpFixedLotSize,
      AccountInfoDouble(ACCOUNT_EQUITY), AccountInfoDouble(ACCOUNT_MARGIN_FREE)
   );
   Comment(status);

   if(!isNewBar) return;

   // 1. Daily Trend Filter
   bool dailyTrendUp = true;
   bool dailyTrendDown = true;

   if(InpRequireDailyTrend && m_dailyEmaHandle != INVALID_HANDLE)
   {
      double dEma[1];
      if(CopyBuffer(m_dailyEmaHandle, 0, 1, 1, dEma) > 0)
      {
         double prevDClose = iClose(_Symbol, PERIOD_D1, 1);
         dailyTrendUp   = (prevDClose > dEma[0]);
         dailyTrendDown = (prevDClose < dEma[0]);
      }
   }

   // 2. Scan H1 for new Order Blocks
   int checkIdx = InpPivotSpan + 1;
   double minDisp = InpMinDisplacementPoints * point;

   // Check Bearish OB
   double checkHigh = iHigh(_Symbol, InpStrategyTimeframe, checkIdx);
   bool isSwingHigh = true;

   for(int k = 1; k <= InpPivotSpan; k++)
   {
      if(iHigh(_Symbol, InpStrategyTimeframe, checkIdx - k) >= checkHigh ||
         iHigh(_Symbol, InpStrategyTimeframe, checkIdx + k) >= checkHigh)
      {
         isSwingHigh = false;
         break;
      }
   }

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

         PrintFormat("[PYRAMID EA] New Bearish OB detected @ %.2f (SL: %.2f)", checkHigh, m_activeOBs[sz].sl);
      }
   }

   // Check Bullish OB
   double checkLow = iLow(_Symbol, InpStrategyTimeframe, checkIdx);
   bool isSwingLow = true;

   for(int k = 1; k <= InpPivotSpan; k++)
   {
      if(iLow(_Symbol, InpStrategyTimeframe, checkIdx - k) <= checkLow ||
         iLow(_Symbol, InpStrategyTimeframe, checkIdx + k) <= checkLow)
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

         PrintFormat("[PYRAMID EA] New Bullish OB detected @ %.2f (SL: %.2f)", checkLow, m_activeOBs[sz].sl);
      }
   }

   // 3. Trade Execution Logic (Base Entry + Risk-Free Pyramid Entry)
   if(openCount >= InpMaxOpenTrades) return;

   double high1 = iHigh(_Symbol, InpStrategyTimeframe, 1);
   double low1  = iLow(_Symbol, InpStrategyTimeframe, 1);

   for(int i = ArraySize(m_activeOBs) - 1; i >= 0; i--)
   {
      if(!m_activeOBs[i].active) continue;

      if(m_activeOBs[i].type == "BEARISH")
      {
         // Retest condition
         if(high1 >= m_activeOBs[i].bottom && high1 <= (m_activeOBs[i].top + 100 * point))
         {
            double slPrice = NormalizeDouble(m_activeOBs[i].sl, digits);
            double slDist  = slPrice - bid;

            if(slDist > 0)
            {
               // Case A: Fresh Base Trade (No existing positions)
               if(openCount == 0)
               {
                  double tpPrice = NormalizeDouble(bid - (slDist * InpTargetRR), digits);
                  double lotSize = GetLotSize(slDist);

                  PrintFormat("[BASE SELL ENTRY] Executing: Bid=%.2f, SL=%.2f, TP=%.2f, Lot=%.2f", bid, slPrice, tpPrice, lotSize);
                  if(m_trade.Sell(lotSize, _Symbol, bid, slPrice, tpPrice, "H1_OB_BASE"))
                  {
                     Print("[BASE SELL Placed! Order: ", m_trade.ResultOrder());
                     m_activeOBs[i].active = false;
                     return;
                  }
               }
               // Case B: Risk-Free Pyramid Entry (1 existing trade, must be in profit >= +2.0R)
               else if(openCount == 1 && InpEnableRiskFreePyramid)
               {
                  double baseTP = 0.0;
                  ENUM_POSITION_TYPE posType;
                  if(IsBaseTradeRiskFree(baseTP, posType) && posType == POSITION_TYPE_SELL)
                  {
                     double tpPrice = (baseTP > 0) ? baseTP : NormalizeDouble(bid - (slDist * InpTargetRR), digits);
                     double lotSize = GetLotSize(slDist);

                     PrintFormat("[PYRAMID SELL ENTRY] Base trade is risk-free! Executing Pyramid: Bid=%.2f, SL=%.2f, TP=%.2f, Lot=%.2f",
                                 bid, slPrice, tpPrice, lotSize);
                     if(m_trade.Sell(lotSize, _Symbol, bid, slPrice, tpPrice, "H1_OB_PYRAMID"))
                     {
                        Print("[PYRAMID SELL Placed! Order: ", m_trade.ResultOrder());
                        m_activeOBs[i].active = false;
                        return;
                     }
                  }
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
               if(openCount == 0)
               {
                  double tpPrice = NormalizeDouble(ask + (slDist * InpTargetRR), digits);
                  double lotSize = GetLotSize(slDist);

                  PrintFormat("[BASE BUY ENTRY] Executing: Ask=%.2f, SL=%.2f, TP=%.2f, Lot=%.2f", ask, slPrice, tpPrice, lotSize);
                  if(m_trade.Buy(lotSize, _Symbol, ask, slPrice, tpPrice, "H1_OB_BASE"))
                  {
                     Print("[BASE BUY Placed! Order: ", m_trade.ResultOrder());
                     m_activeOBs[i].active = false;
                     return;
                  }
               }
               else if(openCount == 1 && InpEnableRiskFreePyramid)
               {
                  double baseTP = 0.0;
                  ENUM_POSITION_TYPE posType;
                  if(IsBaseTradeRiskFree(baseTP, posType) && posType == POSITION_TYPE_BUY)
                  {
                     double tpPrice = (baseTP > 0) ? baseTP : NormalizeDouble(ask + (slDist * InpTargetRR), digits);
                     double lotSize = GetLotSize(slDist);

                     PrintFormat("[PYRAMID BUY ENTRY] Base trade is risk-free! Executing Pyramid: Ask=%.2f, SL=%.2f, TP=%.2f, Lot=%.2f",
                                 ask, slPrice, tpPrice, lotSize);
                     if(m_trade.Buy(lotSize, _Symbol, ask, slPrice, tpPrice, "H1_OB_PYRAMID"))
                     {
                        Print("[PYRAMID BUY Placed! Order: ", m_trade.ResultOrder());
                        m_activeOBs[i].active = false;
                        return;
                     }
                  }
               }
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
