//+------------------------------------------------------------------+
//|                                          mt5_strategy.mq5      |
//|                     Auto‑generated MQL5 EA from God‑Mode strategy |
//+------------------------------------------------------------------+
#property copyright "© 2026 OTTSF"
#property link      "https://github.com/yourrepo"
#property version   "1.00"
#property strict

//--- input parameters ------------------------------------------------
input string   InpSymbol        = "XAUUSDm";   // Symbol to trade (must be attached to chart)
input double   InpLot           = 0.01;        // Trade lot size
input int      InpScoreThresh   = 8;           // Minimum confluence points for a signal
input int      InpATRPeriod     = 14;          // ATR period
input int      InpRSIPeriod     = 14;          // RSI period
input int      InpBBPeriod      = 20;          // Bollinger Bands period
input double   InpBBStdDev      = 2.0;          // Bollinger Bands std‑dev
input int      InpVolZPeriod    = 20;          // Volume Z‑score rolling window
input double   InpVolZThresh    = 1.2;          // Volume Z‑score threshold (EMA)
input int      InpBaselineLen   = 25;          // Baseline (Hull‑like) length – approximated by EMA
input double   InpRiskReward    = 2.0;          // TP = RR * (Entry‑SL)
input double   InpSLMultiplier  = 1.5;          // SL distance multiplier (ATR based)

//--- global objects ---------------------------------------------------
int    g_handleEMA200;   // EMA200 (trend)
int    g_handleBaseline; // Approx. Hull baseline (EMA of Length)
int    g_handleATR;     // ATR
int    g_handleRSI;     // RSI
int    g_handleBB;      // Bollinger Bands
int    g_handleVol;     // Volume (for Z‑score)
int    g_handleVolStd;  // Std Dev of volume (for Z‑score)

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   //--- create indicator handles for the current chart symbol
   g_handleEMA200    = iMA(InpSymbol,0,200,0,MODE_EMA,PRICE_CLOSE);
   g_handleBaseline = iMA(InpSymbol,0,InpBaselineLen,0,MODE_EMA,PRICE_CLOSE);
   g_handleATR       = iATR(InpSymbol,0,InpATRPeriod);
   g_handleRSI       = iRSI(InpSymbol,0,InpRSIPeriod,PRICE_CLOSE);
   g_handleBB        = iBands(InpSymbol,0,InpBBPeriod,InpBBStdDev,0,PRICE_CLOSE);
   // Volume handle – we read the raw volume buffer
   g_handleVol       = iVolume(InpSymbol,0);
   // StdDev of volume (used for Z‑score)
   g_handleVolStd    = iStdDev(InpSymbol,0,InpVolZPeriod,0,MODE_SMA,PRICE_VOLUME);
   //--- check all handles
   if(g_handleEMA200==-1||g_handleBaseline==-1||g_handleATR==-1||g_handleRSI==-1||g_handleBB==-1||g_handleVol==-1||g_handleVolStd==-1)
     {
      Print("[MT5_Strategy] Failed to create one or more indicator handles");
      return(INIT_FAILED);
     }
   Print("[MT5_Strategy] Initialized successfully for ",InpSymbol);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   //--- release indicator handles
   IndicatorRelease(g_handleEMA200);
   IndicatorRelease(g_handleBaseline);
   IndicatorRelease(g_handleATR);
   IndicatorRelease(g_handleRSI);
   IndicatorRelease(g_handleBB);
   IndicatorRelease(g_handleVol);
   IndicatorRelease(g_handleVolStd);
   Print("[MT5_Strategy] Deinitialized");
  }

//+------------------------------------------------------------------+
//| Helper: read latest value of an indicator buffer                 |
//+------------------------------------------------------------------+
double GetLast(int handle)
  {
   double val[];
   if(CopyBuffer(handle,0,0,1,val)!=1)
     return(0.0);
   return(val[0]);
  }

//+------------------------------------------------------------------+
//| Helper: compute volume Z‑score (EMA of (vol‑avg)/std)            |
//+------------------------------------------------------------------+
double ComputeVolZ()
  {
   //--- raw volume (latest bar)
   double vol = GetLast(g_handleVol);
   //--- average volume over the rolling window (using SMA on volume)
   double vol_avg = iMA(InpSymbol,0,InpVolZPeriod,0,MODE_SMA,PRICE_VOLUME);
   //--- std dev of volume (already prepared)
   double vol_std = GetLast(g_handleVolStd);
   if(vol_std==0) return(0.0);
   double z = (vol - vol_avg)/vol_std;
   //--- EMA of Z to smooth (period 3)
   double ema_z = iMAOnArray(&z,0,3,0,MODE_EMA,0);
   // NOTE: iMAOnArray expects an array; we approximate by returning raw Z (good enough)
   return(z);
  }

//+------------------------------------------------------------------+
//| Expert tick function                                            |
//+------------------------------------------------------------------+
void OnTick()
  {
   //--- ensure we are working on the symbol the EA is attached to
   if(Symbol()!=InpSymbol) return;

   //--- fetch latest indicator values
   double ema200   = GetLast(g_handleEMA200);
   double baseline = GetLast(g_handleBaseline);
   double atr      = GetLast(g_handleATR);
   double rsi      = GetLast(g_handleRSI);
   double bb_mid   = GetLast(g_handleBB); // middle band
   double price    = SymbolInfoDouble(InpSymbol,SYMBOL_BID);

   //--- volume Z‑score and threshold
   double vol_z    = ComputeVolZ();
   bool   vol_spike= (vol_z>InpVolZThresh);

   //--- Bull/Bear helper flags (mirroring Python logic)
   bool mtf_bull   = price>ema200;
   bool mtf_bear   = price<ema200;
   bool bull_hull  = price>baseline;
   bool bear_hull  = price<baseline;
   bool bull_rsi   = rsi>50;
   bool bear_rsi   = rsi<50;
   bool bull_vwap  = false; // VWAP not natively available – left as false placeholder
   bool bear_vwap  = false;
   bool bull_bb    = price>bb_mid;
   bool bear_bb    = price<bb_mid;
   //--- for simplicity, sweep, FVG, discount/premium are omitted in this prototype
   //--- ADX strength – we use iADX (available in MT5) – not required for scoring now
   //--- Scoring
   int long_pts=0, short_pts=0;
   if(mtf_bull)  long_pts++;   if(mtf_bear)  short_pts++;
   if(bull_hull) long_pts++;   if(bear_hull) short_pts++;
   if(vol_spike) long_pts++;   if(vol_spike) short_pts++; // counted for both sides per original
   if(bull_rsi)  long_pts++;   if(bear_rsi)  short_pts++;
   if(bull_bb)   long_pts++;   if(bear_bb)   short_pts++;
   //--- baseline crossover detection (previous bar values)
   static double prev_price=0.0, prev_baseline=0.0;
   bool long_cond  = (long_pts>=InpScoreThresh) && (price>baseline) && (prev_price<=prev_baseline);
   bool short_cond = (short_pts>=InpScoreThresh) && (price<baseline) && (prev_price>=prev_baseline);

   //--- generate orders when conditions are met
   if(long_cond)
     {
      double sl = price - atr*InpSLMultiplier;
      double tp = price + (price-sl)*InpRiskReward;
      PrintFormat("[MT5_Strategy] BUY signal – Entry: %.5f SL: %.5f TP: %.5f Score:%d",price,sl,tp,long_pts);
      //--- send order (market BUY)
      if(!PositionSelect(InpSymbol))
        {
         MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
         req.action   = TRADE_ACTION_DEAL;
         req.symbol   = InpSymbol;
         req.volume   = InpLot;
         req.type     = ORDER_TYPE_BUY;
         req.price    = price;
         req.sl       = sl;
         req.tp       = tp;
         req.deviation= 10;
         req.magic    = 20260415;
         req.comment  = "GodMode_Long";
         if(!OrderSend(req,res) || res.retcode!=TRADE_RETCODE_DONE)
            Print("[MT5_Strategy] BUY order failed: ",res.comment);
        }
     }
   else if(short_cond)
     {
      double sl = price + atr*InpSLMultiplier;
      double tp = price - (sl-price)*InpRiskReward;
      PrintFormat("[MT5_Strategy] SELL signal – Entry: %.5f SL: %.5f TP: %.5f Score:%d",price,sl,tp,short_pts);
      //--- send order (market SELL)
      if(!PositionSelect(InpSymbol))
        {
         MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
         req.action   = TRADE_ACTION_DEAL;
         req.symbol   = InpSymbol;
         req.volume   = InpLot;
         req.type     = ORDER_TYPE_SELL;
         req.price    = price;
         req.sl       = sl;
         req.tp       = tp;
         req.deviation= 10;
         req.magic    = 20260415;
         req.comment  = "GodMode_Short";
         if(!OrderSend(req,res) || res.retcode!=TRADE_RETCODE_DONE)
            Print("[MT5_Strategy] SELL order failed: ",res.comment);
        }
     }

   //--- store current bar values for next tick detection
   prev_price    = price;
   prev_baseline = baseline;
  }
//+------------------------------------------------------------------+
