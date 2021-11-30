#!/usr/bin/python3.9
import uuid

import matplotlib
# matplotlib.use('agg') #   non-GUI backend
# matplotlib.use("Qt5agg")
# ! other matplotplib GUI options
matplotlib.use("Qt5agg")
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
import matplotlib.animation as animation
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.widgets import MultiCursor
import mplfinance as mpf
import lib_panzoom as c
import lib_globals as g
import lib_ohlc as o

import lib_listener as kb
from pathlib import Path
from colorama import init
from colorama import Fore, Back, Style
import datetime
import importlib

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
        g.startdate = f"{lastdate}"

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

# g.purch_qty = o.cvars.get("purch_qty") #use
g.buy_fee = o.cvars.get('buy_fee')
g.sell_fee = o.cvars.get('sell_fee')

g.ffmaps_lothresh = o.cvars.get('ffmaps_lothresh')
g.ffmaps_hithresh = o.cvars.get('ffmaps_hithresh')
g.sigffdeltahi_lim = o.cvars.get('sigffdeltahi_lim')

g.capital =  o.cvars.get("capital")
g.purch_pct =  o.cvars.get("purch_pct")/100  

g.purch_qty = g.capital * g.purch_pct

g.bsuid = 0
# g.uid=uuid.uuid4().hex
o.state_wr("purch_qty", g.purch_qty)
g.purch_qty_adj_pct = o.cvars.get("purch_qty_adj_pct")

datatype =o.cvars.get("datatype")

# print(f"---{datatype}")
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
                            columns=['Timestamp', 'buy', 'mclr', 'sell', 'qty', 'subtot', 'tot', 'pnl', 'pct'])
g.cwd = os.getcwd().split("/")[-1:][0]

# * ccxt doesn't yet support CB ohlcv data, so CB and binance charts will be a little off
g.ticker_src = ccxt.binance()
g.spot_src = ccxt.coinbase()
g.conversion = o.get_last_price(g.spot_src)

# * set up the canvas and windows
fig = c.figure_pz(figsize=(o.cvars.get("figsize")[0], o.cvars.get("figsize")[1]), dpi=96)
fig2 = c.figure_pz(figsize=(o.cvars.get("figsize2")[0], o.cvars.get("figsize")[1]), dpi=96)

fig2.add_subplot(111)  # OHLC - top left

if o.cvars.get("columns") == 1:
    fig.add_subplot(311)  # OHLC - top left
    fig.add_subplot(312)  # VOl - mid left
    fig.add_subplot(313)  # Delta - bottom left

if o.cvars.get("columns") == 2:
    fig.add_subplot(321)  # OHLC - top left
    fig.add_subplot(322)  # VOl - mid left
    fig.add_subplot(323)  # Delta - bottom left
    fig.add_subplot(324)  # top right
    fig.add_subplot(325)  # mid right
    fig.add_subplot(326)  # bottom right

ax = fig.get_axes()
ax2 = fig2.get_axes()
ax[0] = ax2[0]

g.num_axes = len(ax)
multi = MultiCursor(fig.canvas, ax, color='r', lw=1, horizOn=True, vertOn=True)

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

print(f"Loop interval set at {g.interval}ms ({g.interval/1000}s)                                         ")

#   ───────────────────────────────────────────────────────────────────────────────────────
#   Attempts to connect via the plot have failed
#   ───────────────────────────────────────────────────────────────────────────────────────
# ! https://github.com/matplotlib/mplfinance/issues/83
#   #   canvas = FigureCanvasQTAgg(fig) #   alt backend, looses crosshaord and stops moving
#   canvas = FigureCanvasTkAgg(fig) #   keeps crosshairs, but stop moving
#   canvas.mpl_connect('motion_notify_event', o.mouse_move)
#   canvas.mpl_connect('key_press_event', o.keypress)

# all_objects = muppy.get_objects()
# sum1 = summary.summarize(all_objects)
# summary.print_(sum1)
# o.waitfor()

def animate(k):
    # importlib.reload(o) # as o

    o.cvars = o.Cvars(g.cfgfile)

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
    working(k)

#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓    LOOP    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
def working(k):

    o.log2file(f"[{g.gcounter}]","counter.log")
    g.gcounter = g.gcounter + 1
    o.state_wr('gcounter',g.gcounter)
    #   num_axes = len(ax)
    g.prev_md5 = o.cvars.this_md5

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

    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + clear all the plots and patches
    # + ───────────────────────────────────────────────────────────────────────────────────────
    for i in range(g.num_axes): ax[i].clear()
    ax_patches = []
    for i in range(g.num_axes): ax_patches.append([])

    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + get the source data as a dataframe
    # + ───────────────────────────────────────────────────────────────────────────────────────

    # * if we are on a 5 minutes ticker, which is published exactly on the 5 minute mark, we don't need to load
    # * every 10 secondsm and we want to load as close to the publish time as possible.  We check the epoch for 5 minutes marks
    # epoch_time = int(time.time())
    # t5 = epoch_time % 300
    # if t5 < 20:   # * we are on a 10 second loop, which takes about 15 seconds, so anythign less that 20 - 25 seconds will not fire twice
    #     g.can_load = True
    #
    # if g.can_load or o.cvars.get("datatype") == "backtest":
    #     # print("Can load")
    #     g.ohlc = o.get_ohlc(g.ticker_src, g.spot_src, since=t.since)
    # ohlc = g.ohlc

    # ! The above is one way to do this.  Below is another.. using cron to create a flag file

    # if g.can_load or o.cvars.get("datatype") == "backtest":
    #     if o.flag_file():
    #         g.ohlc = o.get_ohlc(g.ticker_src, g.spot_src, since=t.since)
    # ohlc = g.ohlc

    # ! the other way is to just set teh interval to 300000 (5m)

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

    g.CLOSE = ohlc['Close'][-1]
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

    ax_patches[0] = o.updateLegend(ax_patches, 0)
    ax_patches[0].append(mpatches.Patch(color='k', label="OHLC"))


    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + make OHLCV df and the default candles plot, and colored volumes
    # + ───────────────────────────────────────────────────────────────────────────────────────
    plots = []  # array of all plots that will be shown
    if o.cvars.get("ohlc"):
        adx = o.cvars.get('loc_ohlc')
        if adx < g.num_axes:  # checks for 2 columns (6 axes) or 1 column (3 axes)
            plots = [mpf.make_addplot(ohlc, ax=ax[adx], type="candle")]

    if o.cvars.get("plots_volume"):
        adx = o.cvars.get('loc_plots_volume')
        if adx < g.num_axes:
            # ohlc['Volume'] = ohlc['Volume']/1000
            if o.cvars.get('volumelines'):
                #   ohlc['Volume'] = o.normalize_col(ohlc['Volume'], -.5,.5)
                plots = o.add_plots(plots, o.get_volume_line(ohlc, ax=ax[adx], type='line'))
                ax_patches[adx].append(mpatches.Patch(color=o.cvars.get('volclrupstyle')['color'], label=f"V-(C-O)"))
                #   ax[adx].set_ylim(-50,50)
            else:
                plots = o.add_plots(plots, o.get_volume(ohlc, ax=ax[adx], type='bar'))
                ax_patches[adx].append(mpatches.Patch(color=o.cvars.get('volclrupstyle')['color'], label=f"Vol Up"))
                ax_patches[adx].append(mpatches.Patch(color=o.cvars.get('volclrdnstyle')['color'], label=f"Vol Dn"))

    # * ───────────────────────────────────────────────────────────────────────────────────────
    # * CREATE ADDITIONAL PLOTS AND ADD TO PLOTS ARRAY
    # * ───────────────────────────────────────────────────────────────────────────────────────
    o.make_steppers(ohlc)  # * fill the stepper data

    # * set trigger boundry for lookback
    ohlc['lblow'] = ohlc['Close'].shift(3).ewm(span=12).mean() * (1-o.cvars.get('lblowpct'))
    ohlc['upperClose'] = ohlc['Close'].ewm(span=12).mean() * (1+o.cvars.get('lblowpct'))
    ohlc['lowerClose'] = ohlc['Close'].ewm(span=12).mean() * (1-o.cvars.get('lblowpct'))
    ohlc['amp'] = abs(ohlc['Close']-ohlc['Close'].shift(1)).ewm(span=12).mean()


    plots = o.plots_lookback(ohlc, plots=plots, ax=ax[0], patches=ax_patches[0])
    plots = o.plots_upperclose(ohlc, plots=plots, ax=ax[0], patches=ax_patches[0])
    plots = o.plots_lowerclose(ohlc, plots=plots, ax=ax[0], patches=ax_patches[0])

    plots = o.plots_amp(ohlc, plots=plots, ax=ax[5], patches=ax_patches[5])

    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "plots_mav" makes moving aveage lines
    # + ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get("plots_mav"):
        adx = o.cvars.get('loc_plots_mav')
        if adx < g.num_axes:
            for m in o.cvars.get("mavs"):
                plots = o.plots_mav(ohlc,
                                    mav     = m['length'],
                                    color   = m['color'],
                                    width   = m['width'],
                                    alpha   = m['alpha'],
                                    plots   = plots,
                                    ax      = ax[adx],
                                    patches = ax_patches[adx]
                                    )
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "rohlc" invert the ohlc
    # + ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get("plots_rohlc"):
        adx = o.cvars.get('loc_plots_rohlc')
        if adx < g.num_axes:
            plots = o.plots_rohlc(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "plots_hilo" makes high/low price lines
    # + ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get("plots_hilo"):
        adx = o.cvars.get('loc_plots_hilo')
        if adx < g.num_axes:
            plots = o.plots_hilo(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])

    if o.cvars.get("plots_hilolim"):
        adx = o.cvars.get('loc_plots_hilolim')
        if adx < g.num_axes:
            plots = o.plots_hilolim(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])

    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "sig*" functions
    # + ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get("plots_sigffmb"):
        adx = o.cvars.get("loc_plots_sigffmb")
        if adx < g.num_axes:
            # o.plots_sigffmb(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])
            plots = o.plots_sigffmb(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])

    if o.cvars.get("plots_sigffmb2"):
        adx = o.cvars.get("loc_plots_sigffmb2")
        if adx < g.num_axes:
            # o.plots_sigffmb2(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])
            plots = o.plots_sigffmb2(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])

    if o.cvars.get("plots_ffmaps"):
        adx = o.cvars.get("loc_plots_ffmaps")
        if adx < g.num_axes:
            plots = o.plots_ffmaps(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])



    if o.cvars.get("plots_sigff"):
        adx = o.cvars.get("loc_plots_sigff")
        if adx < g.num_axes:
            plots = o.plots_sigff(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])

    if o.cvars.get("plots_siglf"):
        adx = o.cvars.get("loc_plots_siglf")
        if adx < g.num_axes:
            plots = o.plots_siglf(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])

    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "plots_bbavg" make average high and low of the short-medium-long bollinger bands
    # +  To do this is makes 3 BB's of different spans
    # + ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get("plots_bbavg"):
        adx = o.cvars.get('loc_plots_bbavg')
        if adx < g.num_axes:
            plots = o.plots_bbavg(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])
        # * ----------------------------------------------------------------
        # * "plots_bb_?" make short-medium-long bollinger bands
        # * ----------------------------------------------------------------
        if o.cvars.get("plots_bb_1"):
            adx = o.cvars.get('loc_plots_bb_1')
            if adx < g.num_axes:
                plots = o.plots_bb(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx],
                                   band=1)
        if o.cvars.get("plots_bb_2"):
            adx = o.cvars.get('loc_plots_bb_2')
            if adx < g.num_axes:
                plots = o.plots_bb(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx],
                                   band=2)
        if o.cvars.get("plots_bb_3"):
            adx = o.cvars.get('loc_plots_bb_3')
            if adx < g.num_axes:
                plots = o.plots_bb(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx], band=3)

    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "plots_2_bbavg" is exactly like "plots_bbavg", but on a different data set ('BB2basis')
    # + ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get("plots_2_bbavg"):
        adx = o.cvars.get('loc_plots_2_bbavg')
        if adx < g.num_axes:
            plots = o.plots_2_bbavg(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])
        # * ----------------------------------------------------------------
        # * "plots_bb_?" make short-medium-long bollinger bands
        # * ----------------------------------------------------------------
        if o.cvars.get("plots_2_bb_1"):
            adx = o.cvars.get('loc_plots_2_bb_1')
            if adx < g.num_axes:
                plots = o.plots_2_bb(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx], band=1)
        if o.cvars.get("plots_2_bb_2"):
            adx = o.cvars.get('loc_plots_2_bb_2')
            if adx < g.num_axes:
                plots = o.plots_2_bb(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx], band=2)
        if o.cvars.get("plots_2_bb_3"):
            adx = o.cvars.get('loc_plots_2_bb_3')
            if adx < g.num_axes:
                plots = o.plots_2_bb(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx], band=3)
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "plots_hilodelta" plots the difference between the HIGH and LOW of each candle
    # + ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get("plots_hilodelta"):
        adx = o.cvars.get('loc_plots_hilodelta')
        if adx < g.num_axes:
            plots = o.plots_hilodelta(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "opcldelta" plots the difference between the OPEN and CLOSE of each candle
    # + ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get("plots_opcldelta"):
        adx = o.cvars.get('loc_plots_opcldelta')
        if adx < g.num_axes:
            plots = o.plots_opcldelta(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "bbDelta" plots the difference between the HI( and LO of the bb3 avg
    # + ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get("plots_bbDelta"):
        adx = o.cvars.get('loc_plots_bbDelta')
        if adx < g.num_axes:
            plots = o.plots_bbDelta(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "deltadelta" plots the difference between the HIGH/LOW and OPEN/CLOSE deltas
    # + ONLY if that data has been created
    # + ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get("plots_opcldelta") and o.cvars.get("plots_hilodelta") and o.cvars.get("plots_deltadelta"):
        adx = o.cvars.get('loc_plots_deltadelta')
        if adx < g.num_axes:
            plots = o.plots_deltadelta(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])

    if o.cvars.get("plots_pt1"):
        adx = o.cvars.get("loc_plots_pt1")
        if adx < g.num_axes:
            plots = o.plots_pt1(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])

    if o.cvars.get("plots_normclose"):
        adx = o.cvars.get("loc_plots_normclose")
        if adx < g.num_axes:
            plots = o.plots_normclose(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])

    if o.cvars.get("plots_macd"):
        # * the EMAs unsed in the MACD has a separate Y-scale so they can't be shown in teh same windows as the MACD
        # * so they are calulated and plotted in a seperatre window, but are not optional for tha MACD

        adx_ema = o.cvars.get("loc_plots_ema")

        if adx_ema < g.num_axes:
            plots = o.plots_macdema(ohlc, plots=plots, ax=ax[adx_ema], patches=ax_patches[adx_ema])

        adx_macd = o.cvars.get("loc_plots_macd")
        if adx_macd < g.num_axes:
            plots = o.plots_macd(ohlc, plots=plots, ax=ax[adx_macd], patches=ax_patches[adx_macd])

    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + The following plots are experimental, useless, or broken
    # + ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get("plots_tholo"):
        adx = o.cvars.get("loc_plots_tholo")
        if adx < g.num_axes:
            plots = o.plots_tholo(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])

    if o.cvars.get("plots_overunder"):
        adx = o.cvars.get("loc_plots_overunder")
        if adx < g.num_axes:
            plots = o.plots_overunder(ohlc, plots=plots, ax=ax[adx], patches=ax_patches[adx])

    ohlc['sigffdelta'] =  range(len(ohlc))
    ohlc['sigffdeltahi'] =  range(len(ohlc))
    plots = o.plots_sigffdelta(ohlc, plots=plots, ax=ax[3], patches=ax_patches[3])
    #
    # bbdelta = ohlc['bbDelta'][-1]
    # # print(bbdelta)
    # if bbdelta > 15:
    #     ax[1].set_facecolor("#ddffdd")
    # else:
    #     ax[1].set_facecolor("#ffffff")

    # + ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    # + ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓    TRIGGERS    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    # + ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    # + ───────────────────────────────────────────────────────────────────────────────────────
    # + "bb3Avg" can pretty much satisfy most filter requirements.  These filters and tests are in 'lib_tests.py'
    # + ───────────────────────────────────────────────────────────────────────────────────────
    if o.cvars.get("triggers"):
        adx = o.cvars.get("loc_trigger")
        if adx < g.num_axes:
            tmp = o.trigger_bb3avg(ohlc, ax=ax[adx])
            plots = o.add_plots(plots, tmp[0])
            plots = o.add_plots(plots, tmp[1])
        # + ───────────────────────────────────────────────────────────────────────────────────────
        # + End of data - now make titles and plot
        # + ───────────────────────────────────────────────────────────────────────────────────────
        ft = o.make_title(type="UNKNOWN", pair=pair, timeframe=timeframe, count="N/A", exchange="Binance",
                          fromdate="N/A", todate="N/A")
        fig.suptitle(ft, color='white')
        fig.patch.set_facecolor('black')
        fig2.patch.set_facecolor('black')

        ax[0].set_title(f"OHCL {add_title} - ({o.get_latest_time(ohlc)}-{t.current.second})", color='white')
        ax[0].set_ylabel("Asset Value (in $USD)", color='white')

    # + add a grid to all charts
    for i in range(g.num_axes):
        ax[i].grid(True, color='grey', alpha=0.3)

    # + add the legends
    for i in range(g.num_axes):
        ax[i].legend(handles=ax_patches[i], loc='upper left', shadow=True, fontsize='x-small')
        ax[i].xaxis.label.set_color('yellow')  # setting up X-axis label color
        ax[i].yaxis.label.set_color('yellow')  # setting up Y-axis label color

        ax[i].tick_params(axis='x', colors='yellow')  # setting up X-axis tick color
        ax[i].tick_params(axis='y', colors='yellow')  # setting up Y-axis tick color

        ax[i].spines['left'].set_color('yellow')  # setting up Y-axis tick color
        ax[i].spines['top'].set_color('yellow')  # setting up above X-axis tick color

    # + save a copy of the final data plotted - used for debugging and viewing
    if o.cvars.get("save"):
        o.cvars.save(ohlc, f"_ohlcdata_{g.instance_num}.json")
        o.cvars.save(g.df_buysell, f"_buysell_{g.instance_num}.json")
        o.cvars.csave(g.state, f"_x_{g.instance_num}.json")

    # + make the chart
    ptype = "candle" if o.cvars.get("ohlc") else "line"

    if o.cvars.get("display"):
        mpf.plot(ohlc, type=ptype, ax=ax[0], addplot=plots, returnfig=True)

    # - mpf.plot returns (at least) fig, but assigning it doesn't work
    # - fig = mpf.plot(ohlc, type.... crashed after the first assgnment.  can't find the canvas or axes anymore, even of fig is defined as global

    # - this is the ONLY way to get a non-blocking timer working
    # - https://stackoverflow.com/questions/16732379/stop-start-pause-in-python-matplotlib-animation

    # ! JWFIX need to have a flag to indicate of ANY pausing is on, and/or diff var as using g.interval causes a 2x load time

    plt.ion()
    plt.gcf().canvas.start_event_loop(g.interval / 1000)

    #* save every transaction
    if g.gcounter == 1:
        header = True
        mode = "w"
    else:
        header = False
        mode = "a"

    # g.df_allrecords = g.df_allrecords.append(ohlc.tail(1),ignore_index=True)
    ohlc.tail(1).to_csv(f"_allrecords_{g.instance_num}.csv",header=header,mode=mode,sep='\t', encoding='utf-8')

    try:
        adf = pd.read_csv(f'_allrecords_{g.instance_num}.csv')
        fn = f"_allrecords_{g.instance_num}.json"
        g.logit.debug(f"Save {fn}")
        o.cvars.save(adf, fn)
        del adf
    except:
        pass

    g.needs_reload = False # * we've reloade from last run after first iteration, so turn off reload flag

    del ohlc
    del g.ohlc
    gc.collect()

    os.system("ps -A --sort -rss -o pid,comm,pmem,rss|grep ohlc >> logs/ps")

    # sum2 = summary.summarize(muppy.get_objects())
    # diff = summary.get_diff(sum1, sum2)
    # summary.print_(diff)

#   frames=<n>, n is completely arbitrary

    # * embaressingly innefficient, but we have 5 minutes between updates.. so nuthin but time :/
    cmd="SET @tots:= 0"
    o.sqlex(cmd)
    cmd=f"UPDATE orders SET fintot = null WHERE session = '{g.session_name}'"
    o.sqlex(cmd)
    cmd=f"UPDATE orders SET runtotnet = credits - fees"
    o.sqlex(cmd)
    cmd=f"UPDATE orders SET fintot = (@tots := @tots + runtotnet) WHERE session = '{g.session_name}'"
    o.sqlex(cmd)

ani = animation.FuncAnimation(fig=fig, func=animate, frames=1086400, interval=g.interval, repeat=False)
mpf.show()
