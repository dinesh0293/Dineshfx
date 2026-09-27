//+------------------------------------------------------------------+
//|                            London_Sweep_NY_Reversal_Indicator.mq5 |
//|                                   Copyright 2026, Dineshfx / AI |
//|                London Liquidity Sweep & NY Reversal Indicator    |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Dineshfx"
#property link      "https://github.com/dinesh0293/Dineshfx"
#property version   "2.00"
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2

#property indicator_label1  "Sweep Sell"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrCrimson
#property indicator_style1  STYLE_SOLID
#property indicator_width1  2

#property indicator_label2  "Sweep Buy"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrLimeGreen
#property indicator_style2  STYLE_SOLID
#property indicator_width2  2

//--- Inputs
input group "=== Session Times (Broker Server Time - Vantage GMT+3) ==="
input string   InpRangeStartTime   = "11:00";    // London Range Start (04:00 AM NY)
input string   InpRangeEndTime     = "15:55";    // Freeze 5 min before NY (08:55 AM NY)
input string   InpTradeStartTime   = "16:00";    // NY Sweep Window Start (09:00 AM NY)
input string   InpTradeEndTime     = "18:30";    // NY Sweep Window End (11:30 AM NY)

input group "=== Sweep Filters ==="
input int      InpMinSweepPoints   = 30;         // Min Sweep Depth ($0.30 on Gold = 30 pts)
input int      InpMaxSweepPoints   = 500;        // Max Sweep Depth ($5.00 on Gold = 500 pts)
input bool     InpRequireDispCandle= true;       // Require Reversal Candle Close

input group "=== Lookback & Visuals ==="
input int      InpHistoryDays      = 10;         // Number of days to draw boxes for
input color    InpBoxColor         = clrDodgerBlue; // Range Box Color
input color    InpHighColor        = clrAqua;       // High Line Color
input color    InpLowColor         = clrOrangeRed;  // Low Line Color
input color    InpMidColor         = clrLightGray;  // 50% Midpoint Line Color

input group "=== Alerts ==="
input bool     InpAlertTerminal    = true;       // Popup Audio/Visual Alert
input bool     InpAlertPush        = false;      // Push Notification to MT5 Mobile

//--- Buffers
double SellBuffer[];
double BuyBuffer[];
datetime g_lastAlertDay = 0;

//+------------------------------------------------------------------+
//| Helper: Convert "HH:MM" string to seconds                        |
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
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, SellBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, BuyBuffer, INDICATOR_DATA);

   PlotIndexSetInteger(0, PLOT_ARROW, 234); // Down Arrow (Sell)
   PlotIndexSetInteger(1, PLOT_ARROW, 233); // Up Arrow (Buy)

   ArraySetAsSeries(SellBuffer, true);
   ArraySetAsSeries(BuyBuffer, true);

   IndicatorSetString(INDICATOR_SHORTNAME, "London_Sweep_Reversal");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                       |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "SWEEP_IND_");
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   if(rates_total < 50) return 0;

   ArraySetAsSeries(time, true);
   ArraySetAsSeries(open, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(close, true);

   int limit = rates_total - prev_calculated;
   if(limit > rates_total - 1) limit = rates_total - 1;
   for(int i = limit; i >= 0; i--)
   {
      SellBuffer[i] = EMPTY_VALUE;
      BuyBuffer[i]  = EMPTY_VALUE;
   }

   int rangeStartSec = TimeToSecondsOfDay(InpRangeStartTime);
   int rangeEndSec   = TimeToSecondsOfDay(InpRangeEndTime);
   int tradeStartSec = TimeToSecondsOfDay(InpTradeStartTime);
   int tradeEndSec   = TimeToSecondsOfDay(InpTradeEndTime);

   datetime currentDayStart = 0;
   int daysProcessed = 0;

   for(int i = 0; i < rates_total - 1 && daysProcessed <= InpHistoryDays; i++)
   {
      MqlDateTime dt;
      TimeToStruct(time[i], dt);
      datetime barDay = time[i] - (dt.hour * 3600 + dt.min * 60 + dt.sec);

      if(barDay != currentDayStart)
      {
         currentDayStart = barDay;
         daysProcessed++;

         datetime dtRangeStart = barDay + rangeStartSec;
         datetime dtRangeEnd   = barDay + rangeEndSec;
         datetime dtTradeStart = barDay + tradeStartSec;
         datetime dtTradeEnd   = barDay + tradeEndSec;

         double dayRangeHigh = -1.0;
         double dayRangeLow  = 99999999.0;
         bool hasData = false;

         for(int j = rates_total - 1; j >= 0; j--)
         {
            if(time[j] >= dtRangeStart && time[j] <= dtRangeEnd)
            {
               if(high[j] > dayRangeHigh) dayRangeHigh = high[j];
               if(low[j] < dayRangeLow)   dayRangeLow  = low[j];
               hasData = true;
            }
         }

         if(!hasData || dayRangeHigh <= dayRangeLow) continue;
         double dayRangeMid = (dayRangeHigh + dayRangeLow) / 2.0;

         // Draw Box for this day
         string prefix = "SWEEP_IND_" + TimeToString(barDay, TIME_DATE) + "_";
         string boxName = prefix + "Box";

         if(ObjectFind(0, boxName) < 0)
         {
            ObjectCreate(0, boxName, OBJ_RECTANGLE, 0, dtRangeStart, dayRangeHigh, dtRangeEnd, dayRangeLow);
            ObjectSetInteger(0, boxName, OBJPROP_COLOR, InpBoxColor);
            ObjectSetInteger(0, boxName, OBJPROP_FILL, true);
            ObjectSetInteger(0, boxName, OBJPROP_BACK, true);
            ObjectSetInteger(0, boxName, OBJPROP_SELECTABLE, false);
         }

         // Look for sweeps in trade window
         bool sweepFired = false;
         for(int k = rates_total - 1; k >= 1; k--)
         {
            if(time[k] >= dtTradeStart && time[k] <= dtTradeEnd && !sweepFired)
            {
               // Bearish Sweep
               if(high[k] > dayRangeHigh && close[k] < dayRangeHigh)
               {
                  double depth = (high[k] - dayRangeHigh) / _Point;
                  bool depthOk = (depth >= InpMinSweepPoints && depth <= InpMaxSweepPoints);
                  bool dispOk  = !InpRequireDispCandle || (close[k] < open[k]);

                  if(depthOk && dispOk)
                  {
                     SellBuffer[k] = high[k] + 20 * _Point;
                     sweepFired = true;

                     if(k == 1 && g_lastAlertDay != barDay)
                     {
                        g_lastAlertDay = barDay;
                        string msg = StringFormat("[SWEEP SELL] %s High Swept! Entry: %.2f, SL: %.2f, TP: %.2f", 
                                                  _Symbol, close[k], high[k] + 0.50, dayRangeMid);
                        if(InpAlertTerminal) Alert(msg);
                        if(InpAlertPush)     SendNotification(msg);
                     }
                  }
               }
               // Bullish Sweep
               else if(low[k] < dayRangeLow && close[k] > dayRangeLow)
               {
                  double depth = (dayRangeLow - low[k]) / _Point;
                  bool depthOk = (depth >= InpMinSweepPoints && depth <= InpMaxSweepPoints);
                  bool dispOk  = !InpRequireDispCandle || (close[k] > open[k]);

                  if(depthOk && dispOk)
                  {
                     BuyBuffer[k] = low[k] - 20 * _Point;
                     sweepFired = true;

                     if(k == 1 && g_lastAlertDay != barDay)
                     {
                        g_lastAlertDay = barDay;
                        string msg = StringFormat("[SWEEP BUY] %s Low Swept! Entry: %.2f, SL: %.2f, TP: %.2f", 
                                                  _Symbol, close[k], low[k] - 0.50, dayRangeMid);
                        if(InpAlertTerminal) Alert(msg);
                        if(InpAlertPush)     SendNotification(msg);
                     }
                  }
               }
            }
         }
      }
   }

   return(rates_total);
}
//+------------------------------------------------------------------+
