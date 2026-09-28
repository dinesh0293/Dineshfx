//+------------------------------------------------------------------+
//|                               H1_OrderBlock_Swing_Indicator.mq5 |
//|                                   Copyright 2026, Dineshfx / AI |
//|              Institutional H1 Order Block & Swing Indicator      |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Dineshfx"
#property link      "https://github.com/dinesh0293/Dineshfx"
#property version   "1.20"
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2

#property indicator_label1  "Bullish OB Alert"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLimeGreen
#property indicator_width1  2

#property indicator_label2  "Bearish OB Alert"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrGold
#property indicator_width2  2

//--- Inputs
input group "=== Swing & Order Block Parameters ==="
input int    InpPivotSpan             = 8;              // Swing Pivot Span (bars)
input double InpMinDisplacementPoints = 800;            // Min Displacement ($8.00 = 800 pts on Gold)
input bool   InpRequireDailyTrend     = false;          // Filter by Daily 50 EMA Trend (false = all H1 OBs)
input int    InpDailyEMAPeriod        = 50;             // Daily EMA Period
input double InpSLBufferPoints        = 200;            // SL Buffer beyond swing wick ($2.00 = 200 pts)

input group "=== Visuals & Clean Display ==="
input bool   InpShowMitigatedBoxes    = true;           // Show Past Mitigated Blocks (Truncated at Retest)
input bool   InpFillBoxes             = false;          // Fill Rectangles (false = Clean outline borders, NO screen blinding)
input int    InpBoxBorderWidth        = 2;              // Box Border Width
input color  InpColorBearishOB        = clrGold;        // Bearish Order Block Color
input color  InpColorBullishOB        = clrMediumSeaGreen; // Bullish Order Block Color
input bool   InpShowLabels            = true;           // Show OB & SL Text Labels
input int    InpMaxHistoryBars        = 300;            // Historical Bars to Scan

//--- Buffers
double BufferBullish[];
double BufferBearish[];

int m_dailyEmaHandle = INVALID_HANDLE;
datetime m_lastCalcTime = 0;

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, BufferBullish, INDICATOR_DATA);
   SetIndexBuffer(1, BufferBearish, INDICATOR_DATA);

   PlotIndexSetInteger(0, PLOT_ARROW, 233); // Arrow up
   PlotIndexSetInteger(1, PLOT_ARROW, 234); // Arrow down

   ArraySetAsSeries(BufferBullish, true);
   ArraySetAsSeries(BufferBearish, true);

   // Wipe any old objects from chart to guarantee pristine display
   ObjectsDeleteAll(0, "H1_OB_");
   ObjectsDeleteAll(0, "H1_EA_OB_");

   if(InpRequireDailyTrend)
   {
      m_dailyEmaHandle = iMA(_Symbol, PERIOD_D1, InpDailyEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   }

   Print("H1_OrderBlock_Swing_Indicator v1.20 initialized cleanly on ", _Symbol);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                       |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "H1_OB_");
   if(m_dailyEmaHandle != INVALID_HANDLE)
      IndicatorRelease(m_dailyEmaHandle);
}

//+------------------------------------------------------------------+
//| Draw or Update an Order Block Rectangle                          |
//+------------------------------------------------------------------+
void DrawOrderBlock(string name, datetime tStart, datetime tEnd, double top, double bottom, color clr)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, tStart, top, tEnd, bottom);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, InpBoxBorderWidth);
      ObjectSetInteger(0, name, OBJPROP_FILL, InpFillBoxes);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
   else
   {
      ObjectSetInteger(0, name, OBJPROP_TIME, 0, tStart);
      ObjectSetInteger(0, name, OBJPROP_TIME, 1, tEnd);
      ObjectSetDouble(0, name, OBJPROP_PRICE, 0, top);
      ObjectSetDouble(0, name, OBJPROP_PRICE, 1, bottom);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, name, OBJPROP_FILL, InpFillBoxes);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, InpBoxBorderWidth);
   }
}

//+------------------------------------------------------------------+
//| Draw or Update an Order Block Text Label (OB Name + SL Price)    |
//+------------------------------------------------------------------+
void DrawOrderBlockLabel(string name, datetime tStart, double price, string text, color clr)
{
   if(!InpShowLabels) return;

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_TEXT, 0, tStart, price);
      ObjectSetString(0, name, OBJPROP_TEXT, text);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetString(0, name, OBJPROP_FONT, "Segoe UI Bold");
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
   else
   {
      ObjectSetInteger(0, name, OBJPROP_TIME, 0, tStart);
      ObjectSetDouble(0, name, OBJPROP_PRICE, 0, price);
      ObjectSetString(0, name, OBJPROP_TEXT, text);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   }
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
   if(rates_total < InpPivotSpan * 4) return(0);

   ArraySetAsSeries(time, true);
   ArraySetAsSeries(open, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(close, true);

   datetime currentBarTime = time[0];
   bool isNewBar = (currentBarTime != m_lastCalcTime);
   if(!isNewBar && prev_calculated > 0) return(rates_total);
   m_lastCalcTime = currentBarTime;

   ObjectsDeleteAll(0, "H1_OB_");

   ArrayInitialize(BufferBullish, EMPTY_VALUE);
   ArrayInitialize(BufferBearish, EMPTY_VALUE);

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double minDisp = InpMinDisplacementPoints * point;
   double slBuf   = InpSLBufferPoints * point;
   double dailyEma[1];

   int scanLimit = MathMin(rates_total - InpPivotSpan * 2, InpMaxHistoryBars);

   for(int pIdx = InpPivotSpan; pIdx <= scanLimit; pIdx++)
   {
      // -------------------------------------------------------------
      // 1. Check for Bearish Order Block
      // -------------------------------------------------------------
      double pivotHigh = high[pIdx];
      bool isSwingHigh = true;

      for(int k = 1; k <= InpPivotSpan; k++)
      {
         if(high[pIdx - k] >= pivotHigh || high[pIdx + k] >= pivotHigh)
         {
            isSwingHigh = false;
            break;
         }
      }

      if(isSwingHigh)
      {
         double dropLow = low[pIdx - 1];
         for(int d = 2; d <= 4; d++)
         {
            if(pIdx - d >= 0 && low[pIdx - d] < dropLow)
               dropLow = low[pIdx - d];
         }

         if((pivotHigh - dropLow) >= minDisp)
         {
            bool trendOk = true;
            if(InpRequireDailyTrend && m_dailyEmaHandle != INVALID_HANDLE)
            {
               if(CopyBuffer(m_dailyEmaHandle, 0, time[pIdx], 1, dailyEma) > 0)
               {
                  if(close[pIdx] > dailyEma[0]) trendOk = false;
               }
            }

            if(trendOk)
            {
               double obTop = pivotHigh;
               double obBottom = MathMin(open[pIdx], close[pIdx]);
               double slPrice = pivotHigh + slBuf;

               // Find departure bar (where price left the box downwards)
               int depBar = -1;
               for(int d = 1; d <= 4; d++)
               {
                  if(pIdx - d >= 0 && close[pIdx - d] < obBottom)
                  {
                     depBar = pIdx - d;
                     break;
                  }
               }

               bool isMitigated = false;
               datetime tEnd = time[0] + (PeriodSeconds() * 15);

               if(depBar != -1)
               {
                  for(int m = depBar - 1; m >= 0; m--)
                  {
                     if(high[m] >= obBottom)
                     {
                        isMitigated = true;
                        tEnd = time[m]; // Truncate cleanly at retest
                        break;
                     }
                  }
               }

               if(!isMitigated || InpShowMitigatedBoxes)
               {
                  datetime tStart = time[pIdx];
                  string obName = StringFormat("H1_OB_SELL_%s", TimeToString(tStart, TIME_DATE|TIME_MINUTES));
                  DrawOrderBlock(obName, tStart, tEnd, obTop, obBottom, InpColorBearishOB);

                  string labelText = StringFormat("H1 SELL OB | SL: %.2f", slPrice);
                  DrawOrderBlockLabel(obName + "_TXT", tStart, pivotHigh + (40 * point), labelText, InpColorBearishOB);

                  BufferBearish[pIdx] = pivotHigh + (50 * point);
               }
            }
         }
      }

      // -------------------------------------------------------------
      // 2. Check for Bullish Order Block
      // -------------------------------------------------------------
      double pivotLow = low[pIdx];
      bool isSwingLow = true;

      for(int k = 1; k <= InpPivotSpan; k++)
      {
         if(low[pIdx - k] <= pivotLow || low[pIdx + k] <= pivotLow)
         {
            isSwingLow = false;
            break;
         }
      }

      if(isSwingLow)
      {
         double rallyHigh = high[pIdx - 1];
         for(int d = 2; d <= 4; d++)
         {
            if(pIdx - d >= 0 && high[pIdx - d] > rallyHigh)
               rallyHigh = high[pIdx - d];
         }

         if((rallyHigh - pivotLow) >= minDisp)
         {
            bool trendOk = true;
            if(InpRequireDailyTrend && m_dailyEmaHandle != INVALID_HANDLE)
            {
               if(CopyBuffer(m_dailyEmaHandle, 0, time[pIdx], 1, dailyEma) > 0)
               {
                  if(close[pIdx] < dailyEma[0]) trendOk = false;
               }
            }

            if(trendOk)
            {
               double obTop = MathMax(open[pIdx], close[pIdx]);
               double obBottom = pivotLow;
               double slPrice = pivotLow - slBuf;

               // Find departure bar (where price left the box upwards)
               int depBar = -1;
               for(int d = 1; d <= 4; d++)
               {
                  if(pIdx - d >= 0 && close[pIdx - d] > obTop)
                  {
                     depBar = pIdx - d;
                     break;
                  }
               }

               bool isMitigated = false;
               datetime tEnd = time[0] + (PeriodSeconds() * 15);

               if(depBar != -1)
               {
                  for(int m = depBar - 1; m >= 0; m--)
                  {
                     if(low[m] <= obTop)
                     {
                        isMitigated = true;
                        tEnd = time[m]; // Truncate cleanly at retest
                        break;
                     }
                  }
               }

               if(!isMitigated || InpShowMitigatedBoxes)
               {
                  datetime tStart = time[pIdx];
                  string obName = StringFormat("H1_OB_BUY_%s", TimeToString(tStart, TIME_DATE|TIME_MINUTES));
                  DrawOrderBlock(obName, tStart, tEnd, obTop, obBottom, InpColorBullishOB);

                  string labelText = StringFormat("H1 BUY OB | SL: %.2f", slPrice);
                  DrawOrderBlockLabel(obName + "_TXT", tStart, pivotLow - (40 * point), labelText, InpColorBullishOB);

                  BufferBullish[pIdx] = pivotLow - (50 * point);
               }
            }
         }
      }
   }

   ChartRedraw(0);
   return(rates_total);
}
//+------------------------------------------------------------------+
