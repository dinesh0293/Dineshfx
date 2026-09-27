//+------------------------------------------------------------------+
//|                               H1_OrderBlock_Swing_Indicator.mq5 |
//|                                   Copyright 2026, Dineshfx / AI |
//|              Institutional H1 Order Block & Swing Indicator      |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Dineshfx"
#property link      "https://github.com/dinesh0293/Dineshfx"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2

#property indicator_label1  "Bullish OB Alert"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLimeGreen
#property indicator_width1  2

#property indicator_label2  "Bearish OB Alert"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrYellow
#property indicator_width2  2

//--- Inputs
input group "=== Swing & Order Block Parameters ==="
input int    InpPivotSpan             = 8;              // Swing Pivot Span (bars)
input int    InpMinDisplacementPoints = 800;            // Min Displacement ($8.00 = 800 pts on Gold)
input bool   InpRequireSweep          = true;           // Require Prior Swing Liquidity Sweep
input bool   InpRequireDailyTrend     = true;           // Filter by Daily 50 EMA Trend
input int    InpDailyEMAPeriod        = 50;             // Daily EMA Period

input group "=== Visuals ==="
input color  InpColorBearishOB        = clrYellow;      // Bearish Order Block Color (The Yellow Box)
input color  InpColorBullishOB        = clrMediumSeaGreen; // Bullish Order Block Color
input int    InpMaxActiveBoxes        = 10;             // Max Active Zones to Draw
input bool   InpSendAlerts            = true;           // Send MT5 Pop-up Alerts on Retest

//--- Buffers
double BufferBullish[];
double BufferBearish[];

int m_dailyEmaHandle = INVALID_HANDLE;

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

   if(InpRequireDailyTrend)
   {
      m_dailyEmaHandle = iMA(_Symbol, PERIOD_D1, InpDailyEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   }

   Print("H1_OrderBlock_Swing_Indicator initialized on ", _Symbol, " Period: ", EnumToString(Period()));
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
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, name, OBJPROP_FILL, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
   else
   {
      ObjectSetInteger(0, name, OBJPROP_TIME, 1, tEnd);
      ObjectSetDouble(0, name, OBJPROP_PRICE, 0, top);
      ObjectSetDouble(0, name, OBJPROP_PRICE, 1, bottom);
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

   int limit = rates_total - prev_calculated;
   if(limit > rates_total - InpPivotSpan * 2)
      limit = rates_total - InpPivotSpan * 2;
   if(limit <= 0) limit = 1;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double minDisp = InpMinDisplacementPoints * point;

   double dailyEma[1];

   for(int i = limit; i >= 0; i--)
   {
      BufferBullish[i] = EMPTY_VALUE;
      BufferBearish[i] = EMPTY_VALUE;

      // 1. Check for Swing High Pivot
      bool isSwingHigh = true;
      double pivotHigh = high[i + InpPivotSpan];
      for(int k = 1; k <= InpPivotSpan; k++)
      {
         if(high[i + InpPivotSpan - k] >= pivotHigh || high[i + InpPivotSpan + k] >= pivotHigh)
         {
            isSwingHigh = false;
            break;
         }
      }

      if(isSwingHigh)
      {
         int pIdx = i + InpPivotSpan;
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
               datetime tStart = time[pIdx];
               datetime tEnd = time[0] + (PeriodSeconds() * 24);

               string obName = StringFormat("H1_OB_SELL_%s", TimeToString(tStart, TIME_DATE|TIME_MINUTES));
               DrawOrderBlock(obName, tStart, tEnd, obTop, obBottom, InpColorBearishOB);
               BufferBearish[pIdx] = pivotHigh + (50 * point);
            }
         }
      }

      // 2. Check for Swing Low Pivot
      bool isSwingLow = true;
      double pivotLow = low[i + InpPivotSpan];
      for(int k = 1; k <= InpPivotSpan; k++)
      {
         if(low[i + InpPivotSpan - k] <= pivotLow || low[i + InpPivotSpan + k] <= pivotLow)
         {
            isSwingLow = false;
            break;
         }
      }

      if(isSwingLow)
      {
         int pIdx = i + InpPivotSpan;
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
               datetime tStart = time[pIdx];
               datetime tEnd = time[0] + (PeriodSeconds() * 24);

               string obName = StringFormat("H1_OB_BUY_%s", TimeToString(tStart, TIME_DATE|TIME_MINUTES));
               DrawOrderBlock(obName, tStart, tEnd, obTop, obBottom, InpColorBullishOB);
               BufferBullish[pIdx] = pivotLow - (50 * point);
            }
         }
      }
   }

   return(rates_total);
}
//+------------------------------------------------------------------+
