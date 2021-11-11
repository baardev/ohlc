#!/bin/python
# + matplotlib.use("Qt5agg")
# + matplotlib.use('Tkagg')
import matplotlib
matplotlib.use('Tkagg')
import lib_globals as g
import datetime as dt
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import MultiCursor
# + import mplfinance as mpf
# + import lib_ohlc as o
# + from lib_cvars import Cvars
# + from lib_cvars import Gvars
import lib_panzoom as c
import pandas as pd
import json
import getopt, sys, os
fromdate = False
todate = False

def days_between(d1, d2):
    d1 = dt.datetime.strptime(d1, "%Y-%m-%d %H:%M:%S")
    d2 = dt.datetime.strptime(d2, "%Y-%m-%d %H:%M:%S")
    return abs((d2 - d1))# + .days)

argv = sys.argv[1:]
try:
    opts, args = getopt.getopt(argv, "-hf:c:", ["help","file","colname"])
except getopt.GetoptError as err:
    sys.exit(2)

input_filename = False
colname = False
for opt, arg in opts:
    if opt in ("-h", "--help"):
        print("-h, --help   this info")
        print("-f, --file  json file of df")
        print("-c, --col  column name")
        sys.exit(0)

    if opt in ("-f", "--file"):
        input_filename = arg
    if opt in ("-c", "--colname"):
        colname = arg

if not colname or not input_filename:
    print('''
    Missing colname or input_filename... examples
        ./liveview.py -f _ohlcdata.json -c Close &
        ./liveview.py -f state.json -c pnl_record_list &
        ./liveview.py -f state.json -c pct_record_list &
        ./liveview.py -f state.json -c pct_gain_list &
    ''')
    exit(1)

fig = c.figure_pz(figsize=(18, 2.5), dpi=96)

x1 = fig.add_subplot(111)  # + OHLC - top left
ax = fig.get_axes()
multi = MultiCursor(fig.canvas, ax, color='r', lw=1, horizOn=True, vertOn=True)

def get_df():
    global fromdate
    global todate
    def state_r(n):
        with open(input_filename) as json_file:
            data = json.load(json_file)
        try:
            return data[n]
        except:
            return False
    try:
        coldat = state_r(colname)
        fromdate = state_r('from')
        todate = state_r('to')
        df = pd.DataFrame(coldat,columns=[colname])
    except:
        df = pd.read_json(input_filename, orient='split', compression='infer')
        fromdate = f"{min(df['Timestamp'])}"
        todate = f"{max(df['Timestamp'])}"

    df['ID'] = range(len(df))
    df.set_index("ID")

    return df

def animate(k):
    num_axes = len(ax)
    df = get_df()
    deltadays = days_between(fromdate, todate)

    for i in range(num_axes):
        ax[i].clear()
        ax[i].set_title(f'{input_filename} -> {colname}  {fromdate} - {todate} (DAYS: {deltadays})')
        ax[i].grid(True, color='grey', alpha=0.3)
        # + ax[i].axhline(y=0.0, color='black')
    ax_patches = []
    for i in range(num_axes):
        ax_patches.append([])





    plt.plot(df['ID'], df[colname])

ani = animation.FuncAnimation(fig=fig, func=animate, frames=86400, interval=1000, blit = False, repeat=True)
plt.show()