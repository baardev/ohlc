#!/usr/bin/python3.9
import matplotlib
matplotlib.use("Qt5agg")
import sys
import getopt
import pandas as pd
from matplotlib.widgets import MultiCursor
import mplfinance as mpf
import lib_panzoom as c

argv = sys.argv[1:]
try:
    opts, args = getopt.getopt(argv, "-hf:", ["help","file="])
except getopt.GetoptError as err:
    sys.exit(2)

input_filename = "_allrecords_0.json" #False

for opt, arg in opts:
    if opt in ("-h", "--help"):
        print("-h, --help   this info")
        print("-f, --file   read from last data file")
        print("-t, --tabloo   use tabloo (def: pandasgui)")
        sys.exit(0)

    if opt in ("-f", "--file"):
        input_filename = arg
    else:
        print("You must enter a file to read")

if not input_filename:
    print("Missing -f <input_filename>")
    exit(1)



print(f"Loading from {input_filename}")

df = pd.read_json(input_filename, orient='split', compression='infer')
df.index = pd.DatetimeIndex(df['Timestamp'])



fig = c.figure_pz(figsize=[18,4], dpi=96)
fig.add_subplot(111)
ax = fig.get_axes()

multi = MultiCursor(fig.canvas, ax, color='r', lw=1, horizOn=True, vertOn=True)

fs = ["Close","bbl0","bbl1","bbl2","bbh0","bbh1","bbh2"]
amin = 1000000
amax = -1000000
for f in fs:
    amin = min(amin, df[f].min())
    amax = max(amax, df[f].max())

ax[0].set_ylim(amin, amax)
# ax[0].set_ylim(df['Close'].min(),df['Close'].max(),)


close_plot = mpf.make_addplot(df['Close'],ax=ax[0],type="line",color="blue",width=1, alpha=1)

bbl0 = mpf.make_addplot(df['bbl0'],ax=ax[0],type="line",color="red",width=1, alpha=0.5)
bbl1 = mpf.make_addplot(df['bbl1'],ax=ax[0],type="line",color="green",width=1, alpha=0.5)
bbl2 = mpf.make_addplot(df['bbl2'],ax=ax[0],type="line",color="blue",width=1, alpha=0.5)

bbh0 = mpf.make_addplot(df['bbh0'],ax=ax[0],type="line",color="red",width=1, alpha=0.5)
bbh1 = mpf.make_addplot(df['bbh1'],ax=ax[0],type="line",color="green",width=1, alpha=0.5)
bbh2 = mpf.make_addplot(df['bbh2'],ax=ax[0],type="line",color="blue",width=1, alpha=0.5)

p1 = mpf.make_addplot(df['bb3avg_buy'], ax=ax[0], scatter=True, color="red", markersize=100, alpha=1, marker=6)  # + ^
p2 = mpf.make_addplot(df['bb3avg_sell'], ax=ax[0], scatter=True, color="green", markersize=100, alpha=1, marker=7)  # + v

plots = [close_plot, p1,p2, bbl0, bbl1, bbl2, bbh0, bbh1, bbh2]
mpf.plot(df, type="line", ax=ax[0], addplot=plots, returnfig=True)
mpf.show()

# plots = o.add_plots(plots,close_plot)
