#!!! THIS IS IS NOT AN HCL FILE, OBVIOUSLY !!!
#* This is a JSON file, but, given that json does not support comments (but I do), having them in the JSON file
#* causes a ton of ugly syntax warnings.  So, this is just renamed to .hcl to make the editor happy.

{
    "creds": {
        "name"    :"coinbase_sandbox" ,
        "provider":"coinbase"         ,
        "apitype" :"sandbox"          ,
        "api_url" :"api-public.sandbox.pro.coinbase.com"
    }
    ,"maxbuys":10   #! mac buys allowed before sell
    ,"purch_qty":0.1
    ,"purch_qty_adj_pct":30
    ,"columns": 2
#    ,"sounds": true
#    ,"mysql": true
    ,"display": true  #! turning off off display only results in a 5% speed increase
    ,"rt_id":0
    ,"bail_option_1":true

  #+ ┌────────────────────────────────────┐
  #+ │ STARTUP ONLY
  #+ └────────────────────────────────────┘
  ,"interval": 0.001      #! can't be 0 or the 'plt' non-blocking pause will loop forever
#  ,"figsize":[18,10]
  ,"figsize":[6,4]
  #+ ┌────────────────────────────────────┐
  #+ │ DATA
  #+ └────────────────────────────────────┘
#  ,"datatype": "random"
  ,"datatype": "backtest"
#  ,"datatype": "live"
  ,"csvname": "results.csv"
  ,"datadir":"/home/jw/src/jmcap/ohlc/data"

  ,"backtestfile":"bb"
  ,"backtestmeta":"bb_DATA"

  #! bb_bear=4572, bb_bull=5981, bb=9468
  ,"datalength":9468      #! MUST be > data-window * 2 - for random/backtest data only:: @5m 1d=288. 1w=2016, 1m=8640
#  ,"datalength":588

   #! for LIVE data 'data-window' value must match 'since' value... i.e. 72 @ 5m = 6hr
  ,"timeframe":"5m"   #! check that the timeframe listed here is support in the o.interval setter in ohlc.py
  ,"datawindow":28    #! MUST be at least as large as the largest bollinger band window
                      #! @5m 1h=12, 6hr=72, 24hr=288
  ,"since":"24:h"     #! hours... make sure there are enough hours to cover the timeframe


  ,"convert_price":    true
                              #!        14.074 for 1 ETH as 1
                              #!        .14074 for purch_qt of 0.01 as 1
                              #!        60000 for aprox price in USD
  ,"offline_price":    60000  #! overrides 'get_last_price()' in lib_ohlc.py
  ,"price_conversion": "BTC/USD"
  ,"pair":             "ETH/BTC"
#  ,"normalize": true

  #+ ┌────────────────────────────────────┐
  #+ │ PLOTS PARAMS
  #+ └────────────────────────────────────┘
  ,"bbcolors":  ["red","green","blue"] #! colors for the fast.medium,slow averages

  ,"bblengths":[12,17,23]           #! length of each bb
  ,"bbstd":[2.1, 2.0, 1.9]         #! MUST BE FP!! standard deviations for each bb on the 2nd BB3 plo]          #! standard deviations for each bb

  ,"bb2lengths": [12,17,23]               #! length of each bb on the 2nd BB3 plot
  ,"bb2std":     [2.1, 2.0, 1.9]         #! MUST BE FP!! standard deviations for each bb on the 2nd BB3 plot


  ,"BBbasis": "Close"
#  ,"BBbasis": "Open"
#  ,"BBbasis": "High"
#  ,"BBbasis": "Low"

   ,"BB2basis": "siglf"   # ! Exception: inputs are all NaN
#   ,"BB2basis": "Close"


#  ,"bbavg_ewm": true                   #! exponential weighted moving average
  ,"bb_ewm_length": {"lower": 10,"middle": 10,"upper": 10}

  ,"tholo_span": 52
  ,"volumeline_span": 5
  ,"volumelines": true

#  ,"MACD_src":   "one_pt"
#  ,"MACD_src":   "Open"
  ,"MACD_src":   "Close"
#  ,"MACD_src":   "High"
#  ,"MACD_src":   "Low"
  ,"EMA_fast":    12
  ,"EMA_slow":    26
  ,"signal_span":  9
  ,"ffmap_span":  2

  ,"bw_filter": "bp"
  ,"lowpctline":15  #! in percent

  ,"filter": {
      "hp": {"name":"highpass", "N":4, "Wn":0.08},
      "lp": {"name":"lowpass",  "N":2, "Wn":0.1},         #! 21 max for data-window 72
      "bp": {"name" : "bandpass", "N" : 4, "Wn": [0.19, 0.21]},
      "bs": {"name":"bandstop", "N":4, "Wn":[0.3,0.4]},   #! can't start from 0.0... freezes
      "ffmx": 1000, #! multiplier
      "lfmx": 1000 #! multiplier
  }

  ,"mbpfilter": {
                 "name":"bandpass",
                 "N":1,   #! 4 is max for datawin of 28
                 "mx" : [  #! this is not used when normalizing the data, mainused for accentuating or damping certain bands
                    12,    # * inverse of 0.083333, center val for bald 1
                    4,     # * inverse of 0.250000, center val for bald 2
                    2.4,   # * inverse of 0.416667, center val for bald 3
                    1.714, # * inverse of 0.583333, center val for bald 4
                    1.333, # * inverse of 0.750000, center val for bald 5
                    1.091  # * inverse of 0.916667, center val for bald 6
                  ],
                 "Wn": [
                    [0.000001, 0.166667 ] ,  #* 6 even divisions of 0-1
                    [0.166667, 0.333333] ,
                    [0.333333, 0.500000],
                    [0.500000, 0.666667] ,
                    [0.666667, 0.833333 ] ,
                    [0.833333, 0.999999 ]

#                    [0.00001,		0.0001]
#                    [0.19999,		0.2],
#                    [0.39999,		0.4],
#                    [0.59999,		0.6],
#                    [0.79999,		0.8],
#                    [0.99999,		0.999999]

#                    [0.00001,		0.999]
#                    [0.19999,		0.2],
#                    [0.39999,		0.4],
#                    [0.59999,		0.6],
#                    [0.79999,		0.8],
#                    [0.99999,		0.999999]

                  ]
                }


  #+ ┌────────────────────────────────────┐
  #+ │ PLOT LOCATIONS
  #+ └────────────────────────────────────┘
  #= ┏━━━┳━━━┓
  #= ┃ 0 ┃ 1 ┃
  #= ┣━━━╋━━━┫
  #= ┃ 2 ┃ 3 ┃
  #= ┣━━━╋━━━┫
  #= ┃ 4 ┃ 5 ┃
  #= ┗━━━┻━━━┛

  ,"deptree": {
        "deltadelta" :{
          "hilodelta" : true,
          "opcldelta" : true
        },
        "bbavg":{
          "bb_1":true,
          "bb_2":true,
          "bb_3":true
        },
        "2_bbavg":{
          "2_bb_1":true,
          "2_bb_2":true,
          "2_bb_3":true
        },
        "macd":{
          "ema":true
        },
        "tholo":{
          "hilodelta" : true
        }
  }

#  ,"loc_ohlc":             5             ,"ohlc": true
  ,"loc_plots_rohlc":             1             ,"plots_rohlc": true
#  ,"loc_plots_mav":        0        ,"plots_mav": true
  ,"loc_plots_ema":        5        ,"plots_ema": true  , "plots_ema_hide": true

#  ,"loc_plots_tholo":      4      ,"plots_tholo": true  #! require hidelta

#  ,"loc_plots_hilodelta":  5  ,"plots_hilodelta": true
#  ,"loc_plots_opcldelta":  5  ,"plots_opcldelta": true
  ,"loc_plots_volume":     4     ,"plots_volume": true
#  ,"loc_plots_deltadelta": 1 ,"plots_deltadelta": true

  ,"loc_plots_bbavg":      0      ,"plots_bbavg": true
  ,"loc_plots_bb_1":       0       ,"plots_bb_1": true
  ,"loc_plots_bb_2":       0       ,"plots_bb_2": true
  ,"loc_plots_bb_3":       0       ,"plots_bb_3": true

#  ,"loc_plots_2_bbavg":      1      ,"plots_2_bbavg": true
#  ,"loc_plots_2_bb_1":       1       ,"plots_2_bb_1": true
#  ,"loc_plots_2_bb_2":       1       ,"plots_2_bb_2": true
#  ,"loc_plots_2_bb_3":       1       ,"plots_2_bb_3": true

#  ,"loc_plots_hilolim":       0       ,"plots_hilolim": true
#  ,"loc_plots_hilo":       4       ,"plots_hilo": true
#  ,"loc_plots_macd":       3       ,"plots_macd": true
#  ,"loc_plots_pnl":        4        ,"plots_pnl": true
#  ,"loc_plots_pct":        5        ,"plots_pct": true
#  ,"loc_plots_pt1":        4        ,"plots_pt1": true
#  ,"loc_plots_normclose":  4        ,"plots_normclose": true
#  ,"loc_plots_overunder":  1        ,"plots_overunder": true
#  ,"loc_plots_sigff":  1        ,"plots_sigff": true
#  ,"loc_plots_siglf":  1        ,"plots_siglf": true

  ,"loc_plots_sigffmb":  2        ,"plots_sigffmb": true, "plots_sigffmb_hide": true
  ,"loc_plots_sigffmap":  2        ,"plots_sigffmap": true

  ,"loc_plots_sigffmb2":  3        ,"plots_sigffmb2": true, "plots_sigffmb2_hide": true
  ,"loc_plots_sigffmap2":  3        ,"plots_sigffmap2": true
  #+ ┌────────────────────────────────────┐
  #+ │ PLOT STYLES
  #+ └────────────────────────────────────┘
#! https://matplotlib.org/stable/gallery/color/named_colors.html

  ,"overunder1style":       {"color":"red",  "width":  1, "alpha": 1.0}
  ,"overunder2style":       {"color":"green",  "width":  1, "alpha": 1.0}
  ,"overunder3style":       {"color":"blue",  "width":  1, "alpha": 1.0}

  # * for the 1st BB3 avg plot




  ,"bbuAvgstyle":    {"color":"yellow",  "width":  1, "alpha": 0.3}
  ,"bbmAvgstyle":    {"color":"magenta", "width":  1, "alpha": 0.3}
  ,"bblAvgstyle":    {"color":"cyan",   "width":  1, "alpha": 0.3



}

  ,"bb1style":       {"color":"red",  "width":  1, "alpha": 0.3}
  ,"bb2style":       {"color":"green",  "width":  1, "alpha": 0.3}
  ,"bb3style":       {"color":"blue",  "width":  1, "alpha": 0.3}
  # * -------------------------------------------------------------

  # * for the 2nd BB3 avg plot
  ,"bbu2Avgstyle":    {"color":"orange",  "width":  1, "alpha": 1.0}
  ,"bbm2Avgstyle":    {"color":"magenta", "width":  1, "alpha": 1.0}
  ,"bbl2Avgstyle":    {"color":"cyan",   "width":  1, "alpha": 1.0}

  ,"bb21style":       {"color":"red",  "width":  1, "alpha": 1.0}
  ,"bb22style":       {"color":"green",  "width":  1, "alpha": 1.0}
  ,"bb23style":       {"color":"blue",  "width":  1, "alpha": 1.0}
  # * -------------------------------------------------------------

  ,"hilostyle":      {"color":"blue",  "width":  2, "alpha": 1}

  ,"hilodeltastyle": {"color":"blue",  "width":  2, "alpha": 1}
  ,"opcldeltastyle": {"color":"grey",  "width":  4, "alpha": 1}
  ,"deltadeltastyle":{"color":"green", "width":  1, "alpha": 1}

  ,"volclrupstyle":  {"color":"green", "width":  2, "alpha": 1} #! 0.5, 0.5 for bars
  ,"volclrdnstyle":  {"color":"red",   "width":  0.5, "alpha": 0.7}

  ,"tholostyle_V":   {"color":"blue",  "width":  1, "alpha": 1}
  ,"tholostyle_I":   {"color":"red",   "width":  1, "alpha": 1}
  ,"tholostyle_R":   {"color":"green", "width":  1, "alpha": 1}
  ,"tholostyle_S":   {"color":"cyan",  "width":  1, "alpha": 1}

  ,"pt1style":       {"color":"pink",    "width": 4, "alpha": 0.3}
  ,"normclosestyle": {"color":"blue",    "width": 4, "alpha": 0.3}

#  ,"EMA_1style":     {"color":"orange", "width": 1, "alpha": 1}
#  ,"EMA_2style":     {"color":"cyan",   "width": 1, "alpha": 1}
  ,"MACDstyle":      {"color":"orange", "width": 1, "alpha": 1}
  ,"siglinstyle":    {"color":"blue",   "width": 1, "alpha": 1}
  ,"histogramstyle": {"color":"purple", "width": 1, "alpha": 1}

  ,"overunderstyle": {"color":"purple", "width": 1, "alpha": 1}

  ,"siglfstyle": {"color":"green", "width": 1, "alpha": 1.0}
  ,"sigffstyle": {"color":"purple", "width": 1, "alpha":1.0}

  ,"sigffmbstyle": {
      "color":["red","olive","blue","cyan", "magenta", "green"],
      "width": 1,
      "alpha": 1.0
    }
  ,"ffmapstyle": {"color":"purple", "width": 1, "alpha":1.0}
  ,"rohlcstyle": {"color":"purple", "width": 1, "alpha":1.0}

  #+ ┌────────────────────────────────────┐
  #+ │ TRIGGER MARKS LOCATIONS
  #+ └────────────────────────────────────┘

  ,"loc_trigger":    0


  ,"mavs": [
     {"length":10, "color":"violet", "width": 2, "alpha": 1}  #! first element is used for ma/low trigger
    ,{"length":20, "color":"brown",  "width": 2, "alpha": 1}
    ,{"length":30, "color":"red",    "width": 2, "alpha": 1}
  ]

  #= ┌────────────────────────────────────┐
  #= │ TRIGGERS AND ORDERS
  #= └────────────────────────────────────┘
  ,"cooldown":2
          #! good pairs
#  ,"testpair":["BUY_CltLowBbavg_ffmapLow","SELL_HgtHiBbavg_CoA"]
  ,"testpair":["BUY_CltLowBbavg_ffmapLow", "SELL_HgtHiBbavg_CoA_ffmapLow"]
  ,"testpair":["BUY_CltLowBbavg_ffmapLow", "SELL_HgtHiBbavg_ffmapLow"]


#  ,"testpair":["BUY_CltLowBbavg","SELL_HgtHiBbavg_CoA"]
#  ,"testpair":["BUY_CltMidBbavg","SELL_CgtPctlim"]
#  ,"testpair":["BUY_ffmapXOlow","SELL_ffmapXOlow"]
#  ,"testpair":["BUY_CltLowBbavg_ffmapLow","SELL_ffmapXUlow_CoA"]
#  ,"testpair":["BUY_always","SELL_always"]

#  , "testpair":["BUY_never","SELL_never"]

  , "triggers": true

  ,"closeXn": 1.01 #! closing > average cost * n

  ,"delta_highlimit_sell": 0.2 #! cyan
  ,"delta_lowlimit_buy":  -0.2 #! magenta

  ,"pt1_highlimit_sell":   0.2 #! cyan
  ,"pt1_lowlimit_buy":    -0.2 #! magenta

  ,"overunder_sell":   0.2 #! cyan
  ,"overunder_buy":    -0.2 #! magenta


  ,"fill":   true
  ,"seed":   99
  ,"mu":     0.0001
  ,"sigma":  0.008
  ,"spread": 0.02    #! for number tweaking

  #+ ┌────────────────────────────────────┐
  #+ │ DEBUG & MISC
  #+ └────────────────────────────────────┘
  ,"save": true
  ,"offline": true
#  ,"epoch_ms_delta": 86400000 #! 1 DAY
#  ,"epoch_ms_delta": 3600000  #! 1 HR
#  ,"epoch_ms_delta": 300000   #! 5 min
  ,"epoch_ms_delta": 60000     #! 1 min

#  ,"logging": 50    #! CRITICAL = 50
#  ,"logging": 50 #! FATAL = CRITICAL
#  ,"logging": 40 #! ERROR = 40
#  ,"logging": 30 #! WARNING = 30
#  ,"logging": 30 #! WARN = WARNING
  ,"logging": 20 #! INFO = 20
#  ,"logging": 10 #! DEBUG = 10
#  ,"logging": 0  #! NOTSET = 0

#  ,"modby": [30,14,0.0]  # used in the lambda 'alter()' function

}
