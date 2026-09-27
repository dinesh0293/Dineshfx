//+------------------------------------------------------------------+
//|                                     NY_Open_Range_Indicator.mq5 |
//|                                  Copyright 2026, Antigravity AI |
//|               New York Open (9:30 AM EST) Breakout Box Indicator |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Antigravity AI"
#property link      "https://metatrader5.com"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2

// Plot Breakout Arrows
#property indicator_label1  "Buy Breakout"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLimeGreen
#property indicator_style1  STYLE_SOLID
#property indicator_width1  2

#property indicator_label2  "Sell Breakout"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrCrimson
#property indicator_style2  STYLE_SOLID
#property indicator_width2  2

//--- Input Parameters
input group "=== Session Times (Broker Server Time) ==="
input string   InpRangeStartTime   = "15:00";    // Range Start Time (e.g. 15:00 = 8:00 AM NY)
input string   InpRangeEndTime     = "16:25";    // Range End Time (e.g. 16:25 = 9:25 AM NY)
input string   InpTradeStartTime   = "16:30";    // NY Open Bell (e.g. 16:30 = 9:30 AM NY)
input string   InpTradeEndTime     = "17:15";    // End of Entry Window (e.g. 17:15 = 10:15 AM NY)

input group "=== Lookback & Visuals ==="
input int      InpHistoryDays      = 10;         // Number of days to draw boxes for
input color    InpBoxColor         = clrDodgerBlue; // Range Box Color
input color    InpHighLineColor    = clrAqua;       // Range High Level Color
input color    InpLowLineColor     = clrOrangeRed;  // Range Low Level Color
input int      InpLineWidth        = 1;          // Range Line Width
input bool     InpFillBox          = true;       // Fill Box with translucent background

input group "=== Alert Settings ==="
input bool     InpAlertTerminal    = true;       // Popup Audio/Visual Alert
input bool     InpAlertPush        = false;      // Push Notification to MT5 Mobile
input bool     InpAlertEmail       = false;      // Email Alert

//--- Indicator Buffers
double BuyBuffer[];
double SellBuffer[];

//--- Internal Tracking
datetime g_lastAlertDay = 0;

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, BuyBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, SellBuffer, INDICATOR_DATA);
   
   PlotIndexSetInteger(0, PLOT_ARROW, 233); // Up Arrow
   PlotIndexSetInteger(1, PLOT_ARROW, 234); // Down Arrow
   
   ArraySetAsSeries(BuyBuffer, true);
   ArraySetAsSeries(SellBuffer, true);
   
   IndicatorSetString(INDICATOR_SHORTNAME, "NY_Open_Range (" + InpRangeStartTime + "-" + InpRangeEndTime + ")");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                       |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "NYORB_");
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Helper: Parse "HH:MM" into seconds from midnight                 |
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
   if(rates_total < 30) return 0;
   
   // We will process day by day
   ArraySetAsSeries(time, true);
   ArraySetAsSeries(open, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(close, true);

   // Initialize newly calculated bars
   int limit = rates_total - prev_calculated;
   if(limit > rates_total - 1) limit = rates_total - 1;
   for(int i = limit; i >= 0; i--)
   {
      BuyBuffer[i] = EMPTY_VALUE;
      SellBuffer[i] = EMPTY_VALUE;
   }

   int rangeStartSec = TimeToSecondsOfDay(InpRangeStartTime);
   int rangeEndSec   = TimeToSecondsOfDay(InpRangeEndTime);
   int tradeStartSec = TimeToSecondsOfDay(InpTradeStartTime);
   int tradeEndSec   = TimeToSecondsOfDay(InpTradeEndTime);

   datetime currentDayStart = 0;
   int daysProcessed = 0;

   // Loop over bars from newest to oldest
   for(int i = 0; i < rates_total - 1 && daysProcessed <= InpHistoryDays; i++)
   {
      MqlDateTime dt;
      TimeToStruct(time[i], dt);
      
      datetime barDay = time[i] - (dt.hour * 3600 + dt.min * 60 + dt.sec);
      if(barDay != currentDayStart)
      {
         currentDayStart = barDay;
         daysProcessed++;
         
         // Calculate Range for this day
         datetime dtRangeStart = barDay + rangeStartSec;
         datetime dtRangeEnd   = barDay + rangeEndSec;
         datetime dtTradeStart = barDay + tradeStartSec;
         datetime dtTradeEnd   = barDay + tradeEndSec;

         double dayRangeHigh = -1.0;
         double dayRangeLow  = 99999999.0;
         bool hasRangeData = false;

         // Find high and low within range window
         for(int j = rates_total - 1; j >= 0; j--)
         {
            if(time[j] >= dtRangeStart && time[j] <= dtRangeEnd)
            {
               if(high[j] > dayRangeHigh) dayRangeHigh = high[j];
               if(low[j] < dayRangeLow)   dayRangeLow  = low[j];
               hasRangeData = true;
            }
         }

         if(!hasRangeData || dayRangeHigh <= dayRangeLow) continue;

         // Draw Box for this day
         string prefix = "NYORB_" + TimeToString(barDay, TIME_DATE) + "_";
         string boxName = prefix + "Box";
         
         if(ObjectFind(0, boxName) < 0)
         {
            ObjectCreate(0, boxName, OBJ_RECTANGLE, 0, dtRangeStart, dayRangeHigh, dtRangeEnd, dayRangeLow);
            ObjectSetInteger(0, boxName, OBJPROP_COLOR, InpBoxColor);
            ObjectSetInteger(0, boxName, OBJPROP_STYLE, STYLE_SOLID);
            ObjectSetInteger(0, boxName, OBJPROP_WIDTH, InpLineWidth);
            ObjectSetInteger(0, boxName, OBJPROP_FILL, InpFillBox);
            ObjectSetInteger(0, boxName, OBJPROP_BACK, true);
            ObjectSetInteger(0, boxName, OBJPROP_SELECTABLE, false);
         }
         else
         {
            ObjectSetInteger(0, boxName, OBJPROP_TIME, 0, dtRangeStart);
            ObjectSetDouble(0, boxName, OBJPROP_PRICE, 0, dayRangeHigh);
            ObjectSetInteger(0, boxName, OBJPROP_TIME, 1, dtRangeEnd);
            ObjectSetDouble(0, boxName, OBJPROP_PRICE, 1, dayRangeLow);
         }

         // Look for breakouts during the trade window
         bool breakoutTriggered = false;
         for(int k = rates_total - 1; k >= 1; k--)
         {
            if(time[k] >= dtTradeStart && time[k] <= dtTradeEnd)
            {
               if(!breakoutTriggered)
               {
                  // Buy Breakout confirmation (candle closed above range high)
                  if(close[k] > dayRangeHigh)
                  {
                     BuyBuffer[k] = low[k] - 20 * _Point;
                     breakoutTriggered = true;

                     // Trigger alert if it just happened on the most recent completed candle (bar index 1)
                     if(k == 1 && g_lastAlertDay != barDay)
                     {
                        g_lastAlertDay = barDay;
                        string msg = StringFormat("[NY Breakout] %s BUY signal! Closed above %.2f at %s", 
                                                  _Symbol, dayRangeHigh, TimeToString(time[k], TIME_MINUTES));
                        if(InpAlertTerminal) Alert(msg);
                        if(InpAlertPush)     SendNotification(msg);
                     }
                  }
                  // Sell Breakout confirmation (candle closed below range low)
                  else if(close[k] < dayRangeLow)
                  {
                     SellBuffer[k] = high[k] + 20 * _Point;
                     breakoutTriggered = true;

                     if(k == 1 && g_lastAlertDay != barDay)
                     {
                        g_lastAlertDay = barDay;
                        string msg = StringFormat("[NY Breakout] %s SELL signal! Closed below %.2f at %s", 
                                                  _Symbol, dayRangeLow, TimeToString(time[k], TIME_MINUTES));
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
