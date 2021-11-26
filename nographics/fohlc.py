#!/usr/bin/python3.9
import uuid

import matplotlib
# matplotlib.use('agg') #   non-GUI backend
# matplotlib.use("Qt5agg")
# ! other matplotplib GUI options
# matplotlib.use("Qt5agg")
# import PyQt5
# matplotlib.use('Tkagg')
# from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
# from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

import gc
import ccxt
import sys
import getopt
import logging
import os
import time
import pandas as pd
# import matplotlib.animation as animation
# import matplotlib.patches as mpatches
# import matplotlib.pyplot as plt
# from matplotlib.widgets import MultiCursor
# import mplfinance as mpf
# import lib_panzoom as c
import flib_globals as g
import flib_ohlc as o

import flib_listener as kb
from pathlib import Path
from colorama import init
from colorama import Fore, Back, Style
import datetime

# import types
# from pympler.tracker import SummaryTracker, muppy
# from pympler import summary
# tracker = SummaryTracker()

init()
# + ≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡
argv = sys.argv[1:]
interval_pause = False
os.system("echo '' > logs/ps")

# g.cfgfile = "config_0.hcl"

try:
    opts, args = getopt.getopt(argv, "-hi:bcrp:j:", ["help", "instance", "batch", "clear", "recover", "pause=","json="])
except getopt.GetoptError as err:
    sys.exit(2)

for opt, arg in opts:
    if opt in ("-h", "--help"):
        print("-i, --instance   instance number")
        print("-b, --batch  batchmode")
        print("-c, --clear  auto clear")
        print("-r, --recover  ")
        print("-j, --json  alt json cfg file")
        print("-p, --pause  interval pause")
        sys.exit(0)

    if opt in ("-i", "--instance number"):
        g.instance_num = f"{arg}"
        g.cfgfile = f"config_{g.instance_num}.hcl"
        g.statefile = f"state_{arg}.json"
    if opt in ("-j", "--json"):
        g.cfgfile = arg
        # * the original cvars was already loaded, which is needed toi get the o.funtions, but we
        # * need to reload cvars with the new config file.  This needs to be split up :/
        o.cvars = o.Cvars(g.cfgfile)
    if opt in ("-b", "--batch"):
        g.batchmode = True
    if opt in ("-c", "--clear"):
        g.autoclear = True
    if opt in ("-r", "--recover"):
        g.recover = True
    if opt in ("-p", "--pause"):
        interval_pause = int(arg)
# + ≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡
print(f"cfgfile: {g.cfgfile}")
print(f"TEST: {o.cvars.get('thisfile')}")
g.time_start = time.time()
g.dbc, g.cursor = o.getdbconn()

g.logit = logging
g.logit.basicConfig(
    filename="logs/ohlc.log",
    filemode='a',
    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
    level=o.cvars.get('logging')
)
stdout_handler = g.logit.StreamHandler(sys.stdout)
# ! Gets error when enabled
# ! extra = {'mod_name':'AAA'}
# ! g.logit = g.logit.LoggerAdapter(g.logit, extra)
# * Did we exit gracefully from the last time?

g.startdate = o.cvars.get('startdate')
# * we get lastdate here, but only use if in recovery

if g.autoclear: #* automatically clear all (-c)
    o.clearstate()
    o.state_wr('isnewrun',True)
    g.gcounter = 0
else:
    if g.recover:  # * automatically recover from saved data (-r)
        o.state_wr('isnewrun', False)
        o.loadstate()
        g.needs_reload = True
        g.gcounter = o.state_r("gcounter")
        g.session_name = o.state_r("session_name")
        lastdate = o.sqlex(f"select order_time from orders where session = '{g.session_name}' order by id desc limit 1",ret="one")[0]
        g.startdate = lastdate

    else:
        if o.waitfor(["Clear Last Data? (y/N)"]): # * True if 'y', defaults to 'N'
            o.clearstate()
            o.state_wr('isnewrun',True)
        else:                                     # * reload old data
            o.state_wr('isnewrun', False)
            o.loadstate()
            g.needs_reload = True
            g.gcounter = o.state_r("gcounter")
            g.session_name = o.state_r("session_name")
            lastdate = o.sqlex(f"select order_time from orders where session = '{g.session_name}' order by id desc limit 1",ret="one")[0]
            g.startdate = lastdate

if o.cvars.get("datatype") == "live":
    o.waitfor(f"!!! RUNNING ON LIVE / {o.cvars.get('datatype')} !!!")

g.logit.info(f"Loading from {g.cfgfile}", extra={'mod_name': 'olhc'})

if o.state_r('isnewrun'):
    o.state_wr("session_name",g.session_name)

o.cvars.prev_md5 = o.cvars.this_md5
g.datawindow = o.cvars.get("datawindow")
g.interval = o.cvars.get("interval")
if interval_pause:
    g.interval = interval_pause

# g.purch_qty = o.cvars.get("purch_qty")
g.buy_fee = o.cvars.get('buy_fee')
g.sell_fee = o.cvars.get('sell_fee')


g.capital =  o.cvars.get("capital")
g.purch_pct =  o.cvars.get("purch_pct")/100  

g.purch_qty = g.capital * g.purch_pct

g.bsuid = 0
# g.uid=uuid.uuid4().hex
o.state_wr("purch_qty", g.purch_qty)
g.purch_qty_adj_pct = o.cvars.get("purch_qty_adj_pct")

datatype =o.cvars.get("datatype")

print(f"---{datatype}")
if datatype == "live":
    g.interval = 300000
else:
    if not o.cvars.get("offline"):
        g.interval = 1000
    else:
        g.interval = 1
    # ! 1sec = 1000
    # ! 300000 = 5min

if interval_pause:
    g.interval = interval_pause

# * create the global buy/sell and all_records dataframes
# g.df_allrecords = pd.DataFrame()
g.df_buysell = pd.DataFrame(index=range(g.datawindow),
                            columns=['Timestamp', 'buy', 'sell', 'qty', 'subtot', 'tot', 'pnl', 'pct'])
g.cwd = os.getcwd().split("/")[-1:][0]

# * ccxt doesn't yet support CB ohlcv data, so CB and binance charts will be a little off
g.ticker_src = ccxt.binance()
g.spot_src = ccxt.coinbase()
g.conversion = o.get_last_price(g.spot_src)

# * set up the canvas and windows
# fig = c.figure_pz(figsize=(o.cvars.get("figsize")[0], o.cvars.get("figsize")[1]), dpi=96)
#
# if o.cvars.get("columns") == 1:
#     fig.add_subplot(311)  # OHLC - top left
#     fig.add_subplot(312)  # VOl - mid left
#     fig.add_subplot(313)  # Delta - bottom left

# if o.cvars.get("columns") == 2:
#     fig.add_subplot(321)  # OHLC - top left
#     fig.add_subplot(322)  # VOl - mid left
#     fig.add_subplot(323)  # Delta - bottom left
#     fig.add_subplot(324)  # top right
#     fig.add_subplot(325)  # mid right
#     fig.add_subplot(326)  # bottom right
#
# ax = fig.get_axes()
# g.num_axes = len(ax)
# multi = MultiCursor(fig.canvas, ax, color='r', lw=1, horizOn=True, vertOn=True)

# * Start the threads and join them so the script doesn't end early
kb.keyboard_listener.start()
if not os.path.isfile(g.statefile): Path(g.statefile).touch()




# + ! https://pynput.readthedocs.io/en/latest/keyboard.html
print(Fore.MAGENTA + Style.BRIGHT)
print("┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
print(f"    INSTANCE: {g.instance_num} / {g.session_name}     ")
print("┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫")
print("┃ Alt + Arrow Down : Decrease interval ┃")
print("┃ Alt + Arrow Up   : Increase interval ┃")
print("┃ Alt + Arrow Left : Jump back 20 tcks ┃")
print("┃ Alt + Arrow Right: Jump fwd 20 tcks  ┃")
print("┃ Alt + End        : Shutdown          ┃")
print("┃ Alt + Delete     : Pause (10s)/Resume┃")
print("┃ Alt + Home       : Verbose/Quiet     ┃")
print("┃ Alt + b          : Buy signal        ┃")
print("┃ Alt + s          : Sell signal       ┃")
print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
o.cclr()

# * ready to go, but launch only on boundry if live
if o.cvars.get('datatype') == "live":
    bt = o.cvars.get('load_on_boundary')
    if not g.epoch_boundry_ready:
        while o.is_epoch_boundry(bt) != 0:
            print(f"{bt - g.epoch_boundry_countdown} waiting for epoch boundry ({bt})", end="\r")
            time.sleep(1)
        g.epoch_boundry_ready = True
        # * we found teh boundry, but now need to wait for teh data to get loaded and updated from the provider
        print(f"{o.cvars.get('boundary_load_delay')} sec. latency pause...")
        time.sleep(o.cvars.get('boundary_load_delay'))
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓    LOOP    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
def working():
    this_logger = g.logit.getLogger()
    if g.verbose:
        this_logger.addHandler(stdout_handler)
    else:
        this_logger.removeHandler(stdout_handler)
    if g.time_to_die:
        g.run_time = time.time() - g.time_start
        o.save_results()
        if not g.time_to_die:
            if g.batchmode:
                exit(0)
            else:
                o.waitfor("I was told to die... goodbye :(")
        else:
            print("Goodbye")
        o.announce(what="finished")
        exit(0)

    o.log2file(f"[{g.gcounter}]","counter.log")
    g.gcounter = g.gcounter + 1
    o.state_wr('gcounter',g.gcounter)
    #   num_axes = len(ax)
    g.prev_md5 = o.cvars.this_md5
    o.cvars = o.Cvars(g.cfgfile)
    if o.cvars.get("datatype") == "backtest":
        g.datasetname = o.cvars.get("backtestfile")
    else:
        g.datasetname = "LIVE"

    if g.prev_md5 != o.cvars.this_md5:
        g.logit.info("Config file updated", extra={'mod_name': 'olhc'})

    pair = o.cvars.get("pair")

    if o.cvars.get("randomize"):
        pair = f"{pair} RANDOMIZED"

    t = o.Times(o.cvars.get("since"))
    add_title = f"[{g.cwd}:{g.buyfiltername}/{g.sellfiltername}:{g.datawindow}]"
    timeframe = o.cvars.get("timeframe")

    retry = 0
    expass = False

    while not expass or retry < 10:
        try:
            # * reinstantiate connections in case of timeout
            g.ticker_src = ccxt.binance()
            g.spot_src = ccxt.coinbase()
            g.ohlc = o.get_ohlc(g.ticker_src, g.spot_src, since=t.since)
            retry = 10
            expass = True
        except Exception as e:
            print(f"Exception error: [{e}]")
            print(f'Something went wrong. Error occured at {datetime.datetime.now()}. Wait for 1 minute.')
            time.sleep(60)
            retry = retry + 1
            expass = False
            # continue
    ohlc = g.ohlc


    # ! ───────────────────────────────────────────────────────────────────────────────────────
    # ! CHECK THE SIZE OF THE DATAFRAME and Gracefully exit on error or command
    # ! ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get('datatype') == "backtest":
        if len(ohlc.index) < g.datawindow:  # ! JWFIX "!=" instead of "<" ?
            g.run_time = time.time() - g.time_start
            o.save_results(data=ohlc)
            if not g.time_to_die:
                if g.batchmode:
                    exit(0)
                else:
                    o.announce(what="finished")

                    o.waitfor("End of data... press enter to exit")
            else:
                print("Goodbye")
                o.announce(what="finished")
            exit(0)

    # ! because mplfinance ALWAYS shows the OHLC, whether you like it or not,
    # ! there needs to be a specific legend and title added

    # ax_patches[0] = o.updateLegend(ax_patches, 0)
    # ax_patches[0].append(mpatches.Patch(color='k', label="OHLC"))


    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + make OHLCV df and the default candles plot, and colored volumes
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # ohlc['voldelta'] = ohlc['Volume']
    # ohlc['voldelta'] = ohlc['Volume'] - (ohlc['Close'] - ohlc['Open'])
    # ohlc['voldelta'] = ohlc['voldelta'].ewm(span=o.cvars.get('volumeline_span')).mean()
    o.make_steppers(ohlc)  # * fill the stepper data
    o.plots_rohlc(ohlc)

    # for m in o.cvars.get("mavs"):
    #     ohlc[f'MAV{m}'] = ohlc["Close"].rolling(m).mean().values
    # ohlc["rohlc"] = ohlc["Close"].max() - ohlc["Close"]

    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "sig*" functions
    # + ───────────────────────────────────────────────────────────────────────────────────────
    o.plots_sigffmb(ohlc)
    o.plots_sigffmb2(ohlc)
    o.plots_sigff(ohlc)
    o.plots_siglf(ohlc)

    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "plots_bbavg" make average high and low of the short-medium-long bollinger bands
    # +  To do this is makes 3 BB's of different spans
    # + ───────────────────────────────────────────────────────────────────────────────────────
    o.add_bolbands(ohlc)
    o.add_2_bolbands(ohlc)
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "plots_hilodelta" plots the difference between the HIGH and LOW of each candle
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # o.get_hilodelta(ohlc)
    # o.get_opcldelta(ohlc)

    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "deltadelta" plots the difference between the HIGH/LOW and OPEN/CLOSE deltas
    # + ONLY if that data has been created
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # o.get_normclose(ohlc)
    # o.get_macdema(ohlc)
    # o.get_macd(ohlc)

    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + The following plots are experimental, useless, or broken
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # o.get_tholo(ohlc)

    # + ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    # + ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓    TRIGGERS    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    # + ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "bb3Avg" can pretty much satisfy most filter requirements.  These filters and tests are in 'lib_tests.py'
    # + ───────────────────────────────────────────────────────────────────────────────────────
    tmp = o.trigger_bb3avg(ohlc)
    # # + save a copy of the final data plotted - used for debugging and viewing
    # if o.cvars.get("save"):
    #     o.cvars.save(ohlc, f"_ohlcdata_{g.instance_num}.json")
    #     o.cvars.save(g.df_buysell, f"_buysell_{g.instance_num}.json")
    #     o.cvars.csave(g.state, f"_x_{g.instance_num}.json")

    #* save every transaction
    # if g.gcounter == 1:
    #     header = True
    #     mode = "w"
    # else:
    #     header = False
    #     mode = "a"
    #
    # ohlc.tail(1).to_csv("_allrecords.csv",header=header,mode=mode,sep='\t', encoding='utf-8')
    #
    # try:
    #     adf = pd.read_csv('_allrecords.csv')
    #     fn = f"_allrecords_{g.instance_num}.json"
    #     g.logit.debug(f"Save {fn}")
    #     o.cvars.save(adf, fn)
    #     del adf
    # except:
    #     pass
    #
    g.needs_reload = False # * we've reloade from last run after first iteration, so turn off reload flag

    del ohlc
    del g.ohlc
    gc.collect()

    os.system("ps -A --sort -rss -o pid,comm,pmem,rss|grep ohlc >> logs/ps")

while g.gcounter < 100:
    working()
