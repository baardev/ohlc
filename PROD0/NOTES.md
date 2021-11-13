## Todo
Check JWFIX notes

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
- oct  3 - nov  2 (bb)      16332300pip install mysqlclient00 - 1634612400

2021-09-05T03:19:00 for https://www.utilities-online.info/epochtime = 1630822740
2021-09-06T00:04:00 for https://www.utilities-online.info/epochtime = 1630897440

more info...
    https://esqsoft.com/javascript_examples/date-to-epoch.htm


## References:

examples of plots for matplotlib
https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.show.html

mpf and mpl
https://github.com/matplotlib/mplfinance/wiki/Acessing-mplfinance-Figure-and-Axes-objects


## python packages needed 

# on Debian (duncanstroud.com)...
to install python3.9 -> https://www.vultr.com/docs/update-python3-on-debian

apt install qtcreator
apt install qtdeclarative5-dev
apt install gnumeric

(may need to use 'pip3' on Debian)

pip install PyQt5
pip install ccxt
pip install matplotlib
pip install mplfinance
pip install pandas-ta 
pip install ta-lib (req. ta-lib src from https://mrjbq7.github.io/ta-lib/install.html)
pip install pynput
pip install pandas
pip install tabloo
pip install coinbasepro
pip install coinbase
pip install colorama
pip install xlsxwriter
pip install mysqlclient (may have needed 'sudo apt-get install libmysqlclient-dev')
pip install scipy
pip install pandasgui   
pip install simplejson

(can't install on 3.5 duncanstroud.com)

pip install MySQLdb
pip install coinbase_python3

# rsync
rsync -avr --exclude 'safe/*' --exclude 'venv/*' /home/jw/src/jmcap/ohlc/ jw@duncanstroud.com:/home/jw/src/jmcap/ohlc/

## remote connecting

Docs: https://en.wikipedia.org/wiki/Xvfb#Usage_examples

needed to ...
sudo ln -s /usr/lib/x86_64-linux-gnu/libxcb-util.so.0 /usr/lib/x86_64-linux-gnu/libxcb-util.so.1

# run virtual screen manager on server
export DISPLAY=:1
Xvfb :1 -screen 0 1910x1280x24 &
fluxbox &
x11vnc -display :1 -bg -nopw -listen localhost -xkb

# tunnel to localhost locally
ssh -N -T -L 5900:localhost:5900 jw@duncanstroud.com

#view locally 
vncviewer -geometry 1920x1280 localhost:5900
vncviewer -encodings 'copyrect tight zrle hextile' localhost:5900 (args didn;t work for me)

# To shutdown vncserver
x11vnc -R stop (doesn;t always work)
ps -ef |grep x11vnc|grep -v grep|awk '{print "kill -9 "$2}'|sh
ps -ef |grep fluxbox|grep -v grep|awk '{print "kill -9 "$2}'|sh
ps -ef |grep /usr/bin/terminator|grep -v grep|awk '{print "kill -9 "$2}'|sh

## Speed tests
with save = 16.05s user 6.54s system 45% cpu 49.787 total
w/o save =  16.14s user 6.42s system 53% cpu 42.476 total

with mem-state = 16.21s user 6.61s system 54% cpu 42.095 total
with file-state: 15.96s user 6.46s system 56% cpu 39.530 total  (faster!?!)


## coinbase specific utils
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
lib_listener.py

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
RUN 
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

## Recovery instruction for fubared boot
https://superuser.com/questions/111152/whats-the-proper-way-to-prepare-chroot-to-recover-a-broken-linux-installation