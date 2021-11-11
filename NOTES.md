## Process to generate backdata

run generator with -d as the starting epoch stamp, and -i as the starting counter
`./ohlc_backdata.py -d 1514812800000 -i 0`

optionally view the data
`./view.py -f data/backdata_ETH+BTC.5m.2018-01-01_13:20:00...2018-01-05_02:35:00.1000_binance_0.json`

merga eall the parts together with -f as the unique filename globber
`./merge.py -f backdata_ETH+BTC.5m. -i 9 -b 2021-10-03 -e 2021-11-05 -o bb `


to convert date string to epoch -> https://esqsoft.com/javascript_examples/date-to-epoch.htm

sample data
- oct  3 - oct 19 (bb_bear) 1633230000 - 1634612400
- oct 19 - nov  2 (bb_bull) 1634612400 - 1634612400
- oct  3 - nov  2 (bb)      1633230000 - 1634612400

2021-09-05T03:19:00 for https://www.utilities-online.info/epochtime = 1630822740
2021-09-06T00:04:00 for https://www.utilities-online.info/epochtime = 1630897440

https://esqsoft.com/javascript_examples/date-to-epoch.htm







## Todo
Check funds before buy


## References:

exampels of plots for matploylib
https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.show.html

mpf and mpl
https://github.com/matplotlib/mplfinance/wiki/Acessing-mplfinance-Figure-and-Axes-objects



## python packages needed

pip install ccxt
pip install matplotlib
pip install mplfinance
pip install pandas-ta
pip install pynput
pip install pandas
pip install tabloo
pip install coinbasepro
pip install colorama
pip install xlsxwriter

(can't install on 3.5 duncanstroud.com)

pip install pandasgui   
pip install MySQLdb
pip install mysqlclient
pip install panzoom
pip install coinbase_python3


## Speed tests
with save = 16.05s user 6.54s system 45% cpu 49.787 total
w/o save =  16.14s user 6.42s system 53% cpu 42.476 total

with mem-state = 16.21s user 6.61s system 54% cpu 42.095 total
with file-state: 15.96s user 6.46s system 56% cpu 39.530 total  (faster!?!)


##
### coinbase specific utils
auth_client.py
public_client.py
cb_cltool.py
cb_order.py
cbtest.py

### Modules
lib_cvars.py
lib_globals.py
lib_ohlc.py
lib_panzoom.py
lib_tests_class.py

### Folders
assets
configs
data
logs
records
safe
ship

### OHLC utils
RUN
ohlc.py
merge.py
mkLIVE
pread.py
view.py
ohlc_backdata.py
liveview.py

### Misc utils
batch.sh
test_cb.sh
launch.sh
rep
test.py

### Config files
config_0.hcl
state_0.json

### Output
results.csv
results.xls

### Docs
NOTES.md

### Backups
ohlc.zip





# --------------------------------------------------------
Run Name: ohlc/cotoneaster
b01.C<BBAL / s01.C>A&C>BBAH

Total % increase: 26.299028834534724
Total % HODL: xxx
Final % : xxx
$ Total Profit: 33.01679999999997
Instance: 0
Max Cont. Buys: 26
Delta Days: 6 days, 5:35:00
Total buys: 103
Total sells: 18
runtime (m): 33.1
Pair: ETH/BTC
Data window: 72
Buy/sell filter: [b01.C<BBAL / s01.C>A&C>BBAH]
Config ID: configs/0_958c9777745f4f288422b3875ddb37d0.hcl
Date: 2021-11-03 16:57:20
Timeframe: 5m


-----------------
b01.C<BBAL / s01.C>BBAH

Total % increase: 15.521933867801863
Total % HODL: -33783.99999999997
Final % : 33799.52193386777
$ Total Profit: -8.27240000000009
Instance: 0
Max Cont. Buys: 22
Delta Days: 4 days, 1:05:00
Total buys: 78
Total sells: 13
runtime (m): 23.5
Pair: ETH/BTC
Data window: 72
Buy/sell filter: [b01.C<BBAL / s01.C>A&C>BBAH]
Config ID: configs/0_48d30f1b91134b299517c1523fb4fbb1.hcl
Date: 2021-11-03 17:16:35
Timeframe: 5m
