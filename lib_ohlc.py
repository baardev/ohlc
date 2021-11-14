import os
import json
import random
import calendar
import uuid
from datetime import datetime
import sys
import numpy as np
import pandas as pd
import pandas_ta as ta
import talib as talib
from lib_cvars import Cvars  # ! used in ohlc.py, not here
import mplfinance as mpf
import matplotlib.patches as mpatches
import MySQLdb as mdb
import math
import datetime as dt
from lib_tests_class import Tests
import csv
import lib_globals as g
from shutil import copyfile
import subprocess
from subprocess import Popen
from colorama import Fore, Back, Style  # ! https://pypi.org/project/colorama/
import traceback
from scipy import signal

extra = {'mod_name': 'lib_olhc'}


# + -------------------------------------------------------------
# +  CLASSES
# + -------------------------------------------------------------
class Times:
    def __init__(self, hours):
        self.since = 60 * 3
        self.current = datetime.now()
        self.__from_now(hours)

    def __from_now(self, hoursback):
        now = datetime.utcnow()
        unixtime = calendar.timegm(now.utctimetuple())
        _min = 60 * hoursback
        since_minutes = _min * 60
        self.since = (unixtime - since_minutes) * 1000  # ! UTC timestamp in milliseconds


def get_seconds_now():
    first_date = datetime(1970, 1, 1)
    time_since = datetime.now() - first_date
    seconds = int(time_since.total_seconds())
    return seconds

# + -------------------------------------------------------------
# +  ORDERING
# + -------------------------------------------------------------
def filter_order(order):
    tord = {}
    supported_actions = ['market', 'sellall']

    if supported_actions.count(order['order_type']) == 0:
        print(f"{order['order_type']} not yet supported")
        exit(1)
    else:
        tord['type'] = tryif(order, 'order_type', False)
        tord['side'] = tryif(order, 'side', False)
        tord['pair'] = tryif(order, 'pair', False)
        tord['size'] = tryif(order, 'size', 0)
        tord['price'] = tryif(order, 'price', False)
        tord['stop_price'] = tryif(order, 'stop_price', 0)
        tord['upper_stop_price'] = tryif(order, 'upper_stop_price', 0)

        tord['funds'] = False
        tord['uid'] = tryif(order, 'uid', -1)

    tord['state'] = tryif(order, 'state', "UNKNOWN")
    tord['order_time'] = tryif(order, 'order_time', get_datetime_str())

    tord['pair'] = tord['pair'].replace("/", "-")  # ! adjust for coinbase name
    # * this converts the field names into the command line switcheS -P, -z, etc
    argstr = ""
    for key in tord:
        if tord[key]:
            try:
                try:  # ! skip over missing g.cflds fields, lile 'state' and 'record_time'
                    argstr = argstr + f" {g.cflds[key]} {tord[key]}"
                except Exception as ex:
                    pass
            except KeyError as ex:
                handleEx(ex, f"{tord}\n{key}")
                exit(1)
            except Exception as ex:
                handleEx(ex, f"{tord}\n{key}")
                exit(1)

    argstr = f"/home/jw/src/jmcap/ohlc/cb_order.py {argstr}"
    return tord, argstr


def update_db(tord, nsecs):
    argstr = ""
    for key in tord:
        vnp = f"{key} = {tosqlvar(tord[key])}"
        argstr = f"{argstr},{vnp}"

    if cvars.get("mysql"):
        # g.dbc, g.cursor = getdbconn()

        cmd = f"insert into orders (uid) values ('{nsecs}')"
        sqlex(cmd)
        g.logit.debug(cmd)
        cmd = f"UPDATE orders SET {argstr[1:]} where uid='{nsecs}'".replace("'None'", "NULL")
        sqlex(cmd)
        g.logit.debug(cmd)

        # g.cursor.close()  # ! JWFIX - open and close here?

    return


def ffix(f):
    try:
        df = float(f)
    except Exception as ex:
        return f

    m = 1000000
    cf = np.round(int(df * m)) / m

    print(f"from/to: {df:10f} -> {cf:10f}")
    return cf


def tosqlvar(v):
    if not v:
        v = None
    v = f"'{v}'"
    return v


def exec_io(argstr, timeout=10):
    command = argstr.split()
    cp = Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    rs = ""
    try:
        output, errors = cp.communicate(timeout=timeout)
        rs = output.strip()
    except Exception as ex:
        cp.kill()
        print("Timed out...")

    if len(rs) < 20:
        g.logit.info(f"SENT: [{argstr}]")
        g.logit.info(f"RECIEVED: {rs}")
        g.logit.info(f"!!EMPTY RESPONSE!! Exiting:/")
        exit(1)

        # = rs = {
        # = "message": "missing response... continuing",
        # = "settled": True,
        # = "order": "missing",
        # = "resp": ["missing"]
        # = }

    return rs


def orders(order, **kwargs):
    nsecs = get_seconds_now()
    tord, argstr = filter_order(order)  # * filters out the unnecessary fields dependinG on order type

    # * submit order to remote proc, wait for replays

    if cvars.get('offline'):
        tord['fees'] = 0
        tord['session'] = g.session_name
        tord['state'] = True
        tord['record_time'] = get_datetime_str()
    else:
        g.logit.info(pcTOREM() + argstr + pcCLR(), extra={'mod_name': 'lib_olhc'})
        sys.stdout.flush()

        # - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓

        # ! This is where the data from cb_order.py is returned as an array (json serialized)...
        # ! in cb_order.py teh array is called 'rs_ary', and it si the last output of the program
        # = Because the objecss returned from coinbase, or any array that has Decimal types, can't be serialized,
        # = the pickled objects are saved as files, and these input_filenames are return in rs_ary
        # - {
        # -     "message": "Settled after 1 attempt",
        # -     "settled": true,
        # -     "order": "records/B_1635517292.ord",
        # -     "resp": [
        # -         "records/B_1635517292.ord.r_0"
        # -     ]
        # - }

        ufn = exec_io(argstr)

        # - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓

        g.logit.info(pcFROREM() + ufn + pcCLR(), extra={'mod_name': 'lib_olhc'})
        cclr()
        try:
            rs_ary = json.loads(ufn)  # * load the array of pickled files
            rs_order = pd.read_pickle(rs_ary['order'])
            fees = 0
            for r in rs_ary['resp']:
                rs_resp = pd.read_pickle(r)
                try:
                    fees = fees + float(rs_resp['fill_fees'])
                except Exception as ex:
                    pass
            tord['fees'] = calcfees(rs_ary)
            tord['session'] = g.session_name
            tord['state'] = rs_order["settled"]
            tord['record_time'] = get_datetime_str()
        except Exception as ex:
            handleEx(ex, f"len(ufn)={len(ufn)}")
            g.logit.info(pcFROREM() + ufn + pcCLR())

    update_db(tord, nsecs)
    return

def get_running_bal():
    # g.dbc, g.cursor = getdbconn()
    cmd = f"select * from orders where session = '{g.session_name}'"
    rs = sqlex(cmd)
    # g.cursor.close()  # ! JWFIX - open and close here?

    c_id = 0
    c_uid = 1
    c_pair = 2
    c_fees = 3
    c_price = 4
    c_stop_price = 5
    c_upper_stop_price = 6
    c_size = 7
    c_funds = 8
    c_record_time = 9
    c_order_time = 10
    c_side = 11
    c_type = 12
    c_state = 13
    c_session = 14

    buys = []
    sells = []

    tot_profit = 0
    i = 1
    res = False
    for r in rs:
        aclose = r[c_price]
        aside = r[c_side]
        aqty = r[c_size]
        adate = r[c_order_time]
        v =aqty*aclose
        if aside == "buy":
            # print(Fore.RED + f"Bought {aqty:3.2f} @ {aclose:6.4f} =  {(aqty*aclose):=6.4f}"+Fore.RESET)
            buys.append(v)
        if aside == "sell":
            # print(Fore.GREEN + f"  Sold {aqty:3.2f} @ {aclose:6.4f} = {(aqty*aclose):6.4f}"+Fore.RESET)
            sells.append(v)
            profit = sum(sells) - sum(buys)
            # print(Fore.YELLOW+f"PROFIT:------------------ {sum(sells)} - {sum(buys)} = {profit}"+Fore.RESET)
            res = Fore.CYAN + f"[{i:04d}] {Fore.CYAN}{adate} {Fore.YELLOW}${profit:6.4f}" + Fore.RESET
        i += 1
    return res


def handleEx(ex, related):
    print(pcERROR())
    print("───────────────────────────────────────────────────────────────────────")
    print("Related: ", related)
    print("---------------------------------------------------------------------")
    print("Exception: ", ex)
    print("---------------------------------------------------------------------")
    for e in traceback.format_stack():
        print(e)
        print("───────────────────────────────────────────────────────────────────────")
    cclr()
    exit()
    return


def clearstate():
    state_wr('session_name', "noname")
    state_wr('ma_low_holding', False)
    state_wr('ma_low_sellat', 1e+10)
    state_wr("open_buyscanbuy", True)
    state_wr("open_buyscansell", False)



    state_wr("from", False)
    state_wr("to", False)
    state_wr("tot_buys", 0)
    state_wr("tot_sells", 0)
    state_wr("max_qty", 0)
    state_wr("first_buy_price", 0)
    state_wr("last_buy_price", 0)

    state_wr("largest_run_count", 0)
    state_wr("last_run_count", 0)
    state_wr("current_run_count", 0)

    state_wr("curr_qty", 0)
    state_wr("delta_days", 0)
    state_wr("purch_qty", False)
    state_wr("run_counts", [])

    state_wr('open_buys', [])
    state_wr('qty_holding', [])


    state_wr("pct_gain_list", [])
    state_wr("pct_record_list", [])
    state_wr("pnl_record_list", [])

    state_wr("last_avg_price",float("Nan"))

    state_wr("pnl_running", float("Nan"))
    state_wr("pct_running", float("Nan"))


# + -------------------------------------------------------------
# +  UTILS
# + -------------------------------------------------------------

def get_a_word():
    with open("data/words.txt", "r") as w:
        words = w.readlines()
    i = random.randint(0, len(words) - 1)
    g.wordlabel = words[i]
    return words[i].strip()

def flag_file(**kwargs):
    state = False
    ff = "/tmp/flagfile"
    if os.path.isfile(ff):
        state = True
        os.remove(ff)
    return state

def announce(**kwargs):
    if cvars.get("sounds"):
        try:
            what = kwargs['what']
            rs = os.system(f"aplay assets/pluck.wav > /dev/null 2>&1") if what == "buy" else False
            rs = os.system(f"aplay assets/ping.wav > /dev/null 2>&1") if what == "sell" else False
            rs = os.system(f"aplay assets/ready.wav > /dev/null 2>&1") if what == "finished" else False
        except Exception as ex:
            return False
    else:
        return False


def save_results(**kwargs):
    try:
        data = kwargs['data']
    except:
        data=False

    def createcsv(csvname, print_order):
        fieldnames = print_order.keys()
        with open(csvname, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

    findat = {}
    findat["Run Name"] = f"{g.cwd}/{g.wordlabel}".strip()
    findat["Dataset"] = g.datasetname
    findat["Algos"] = f"{g.buyfiltername} / {g.sellfiltername}".strip()
    findat["Pair"] = cvars.get('pair').strip()
    findat["Total buys"] = g.tot_buys
    findat["Total sells"] = g.tot_sells
    findat["cooldown"] = cvars.get('cooldown')
    findat["purch_qty_adj_pct"] = cvars.get('purch_qty_adj_pct')
    uid = f"{g.instance_num}_{uuid.uuid4().hex}"
    tfn = f"configs/{uid}.hcl"
    findat["Config ID"] = tfn
    findat["Date"] = get_datetime_str()
    findat["Timeframe"] = cvars.get('timeframe')
    findat["Instance"] = g.instance_num
    findat["bblength"] = cvars.get('bblengths')
    findat["bbstd"] = cvars.get('bbstd')
    findat["datalength"] = cvars.get('datalength')
    findat["rt_id"] = cvars.get('rt_id')
    findat["maxbuys allowed"] = cvars.get('maxbuys')
    findat["lowpctline"] = cvars.get('lowpctline')
    findat["Data window"] = g.datawindow
    tpi = state_r('pct_running')
    findat["Total % increase"] = tpi

    try:
        tph = ((state_r('last_sell_price') / state_r('first_buy_price')) - 1) * 100
    except:
        tph = 0

    findat["Total % HODL"] = tph
    tpf = tpi - tph
    findat["Final %"] = tpf
    findat["Total buys"] = g.tot_buys
    findat["Total sells"] = g.tot_sells

    if (len(state_r('run_counts'))) > 0:
        findat["Max Cont. Buys"] = max(state_r('run_counts'))
    else:
        findat["Max Cont. Buys"] = "N/A"

    findat["$ Total Profit"] = state_r('pnl_running')

    findat["Delta Days"] = state_r('delta_days')
    findat["runtime (m)"] = int(g.run_time / 6) / 10
    findat["Message"] = "OK"

    print("▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓")

    fn = f"xout_{cvars.get('rt_id')}.txt"
    file1 = open(fn, "w")

    print_order_keys = [
        "rt_id"
        , "Dataset"
        , "Delta Days"
        , "Algos"
        , "Total buys"
        , "Total sells"
        , "Max Cont. Buys"
        , "cooldown"
        , "lowpctline"
        , "bblength"
        , "bbstd"
        , "Total % increase"
        , "$ Total Profit"
        , "Data window"
        , "maxbuys allowed"

        , "Total % HODL"
        , "Final %"
        , "Run Name"
        , "Pair"
        , "purch_qty_adj_pct"
        , "Config ID"
        , "Date"
        , "Timeframe"
        , "Instance"
        , "datalength"
        , "runtime (m)"
        , "Message"
    ]
    print_order = {}
    for k in print_order_keys:
        print_order[k] = findat[k]

    for key in print_order:
        str = f"{key}: {print_order[key]}"
        file1.write(str + "\n")
    file1.close()

    print("▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓")

    csvname = "/home/jw/src/jmcap/ohlc/" + cvars.get('csvname')
    if not os.path.isfile(csvname): createcsv(csvname, print_order)
    with open(csvname, 'a') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=print_order_keys)
        writer.writerow(print_order)

    copyfile(f"config_{g.instance_num}.hcl", f"/home/jw/src/jmcap/ohlc/{tfn}")

    os.system("ssconvert results.csv results.xls")

    #* now save the df_allrecords

    fn = f"_allrecords_{g.instance_num}.json"
    g.logit.debug(f"Save {fn}")
    cvars.save(g.df_allrecords, fn)
    g.logit.info(f"Results saved in {csvname}")


def get_datetime_str():
    now = datetime.now()  # + current date and time
    # + year = now.strftime("%Y")
    # + month = now.strftime("%m")
    # + day = now.strftime("%d")
    # + time = now.strftime("%H:%M:%S")
    # + date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
    date_time = now.strftime("%Y-%m-%d %H:%M:%S")
    # + print("date and time:",date_time)
    return date_time


# def mouse_move(event):
#     x, y = event.xdata, event.ydata
#     # + print(f"Mouse: x / y: {x} / {y}")
#     # + motion_notify_event: xy=(4, 420) xydata=(None, None) button=None dblclick=False inaxes=None Figure(1800x1002)

#
# def keypress(event):
#     # + https: // matplotlib.org / stable / gallery / event_handling / keypress_demo.html
#     print('press', event.key)
#     sys.stdout.flush()
#     if event.key == 'p':
#         g.interval = 1000
#         print("interval = 1000")
#     if event.key == 'o':
#         g.interval = 0
#         print("interval = 0")

    # + visible = xl.get_visible()
    # + xl.set_visible(not visible)
    # + fig.canvas.draw()

    print(event)


def state_wr(n, v):
    if g.state:  # + array in mem exists
        g.state[n] = v
    else:
        try:
            with open(g.statefile) as json_file:
                data = json.load(json_file)
        except Exception as ex:
            handleEx(ex, f"Check the file '{g.statefile}' (for ex. at 'https://jsonlint.com/)'")
            exit(1)
        data[n] = v
        try:
            with open(g.statefile, 'w') as outfile:
                json.dump(data, outfile, indent=4)
        except Exception as ex:
            handleEx(ex, f"Check the file '{g.statefile}' (for ex. at 'https://jsonlint.com/)'")
            exit(1)
        data[n] = v


def state_ap(listname, v):
    if g.state:  # + array in mem exists
        g.state[listname].append(v)
    else:
        with open(g.statefile) as json_file:
            data = json.load(json_file)
        data[listname].append(v)
        with open(g.statefile, 'w') as outfile:
            json.dump(data, outfile, indent=4)


def state_r(n, **kwargs):
    if g.state:  # + array in mem exists
        return g.state[n]
    else:
        try:
            with open(g.statefile) as json_file:
                data = json.load(json_file)
            return data[n]
        except:
            print(f"Attempting to read '{n}' from '{g.statefile}")
            return False


def cfgfile_r(n):
    c = Cvars(g.cfgfile)
    i = c.get("interval")
    print("i", i)
    return (i)


def waitfor(data=["Here Now"], ext=False, **kwargs):
    # + * print and leave
    if ext:
        print(data)
        exit()

    stop_at = True  # + * True be default
    try:
        stop_at = kwargs['stop_at']  # + * but checks for override
    except:
        pass  # + * not overridden to just contiue
    # + with open('_tmp', 'w') as outfile:  # + * saves the data sent in as rarg to a JSON file (why??)
    sdata = json.dumps(data)
    # + with open('_tmp', 'r') as file:    # + * then read it in again!!??
    # + sdata = file.read()

    if stop_at:
        print("waiting...\n")
        # + x=input(sdata)
        x = input(sdata)
        if x == "x":
            exit()
        if x == "n":
            return False
        if x == "y":
            return True
    else:
        print(sdata)


def add_plots(target, source):  # * lists

    # * first check if source exists
    if source:
        for p in source:
            target.append(p)
    return target


def cycle_in_range(number, amin, amax, invert=False):
    try:
        mod_num = number % amax
    except:
        mod_num = 0

    try:
        mod_num2 = number % (amax * 2)
    except:
        mod_num2 = 0

    new_val1 = abs(mod_num2 - (mod_num * 2))

    old_min = 0
    old_min = 0
    old_max = amax
    new_max = amax
    new_min = amin

    try:
        new_value = ((new_val1 - old_min) / (old_max - old_min)) * (new_max - new_min) + new_min
    except:
        new_value = 0

    new_value = amax - new_value if invert else new_value

    return (round(new_value))


def list_avg(purchase_price_list, purchase_quantity_list):
    # + waitfor([purchase_price_list,purchase_quantity_list])
    totalcost = 0
    totalcount = 0
    for price in range(len(purchase_price_list)):
        totalcost = totalcost + (purchase_price_list[price] * purchase_quantity_list[price])
    for quantity in range(len(purchase_quantity_list)):
        totalcount = totalcount + purchase_quantity_list[quantity]

    try:
        averagecost = totalcost / totalcount
    except:
        return 0, 0, 0
    # + waitfor(["insde",totalcost, totalcount, averagecost])
    return [totalcost, totalcount, averagecost]


def days_between(d1, d2):
    try:
        d1 = dt.datetime.strptime(d1, "%Y-%m-%d %H:%M:%S")
        d2 = dt.datetime.strptime(d2, "%Y-%m-%d %H:%M:%S")
        return abs((d2 - d1))  # + .days)
    except:
        return 0


def make_title(**kwargs):
    atype = kwargs['type']
    pair = kwargs['pair']
    timeframe = kwargs['timeframe']
    count = kwargs['count']
    exchange = kwargs['exchange']
    fromdate = kwargs['fromdate']
    todate = kwargs['todate']
    livect = f"({g.gcounter}/{cvars.get('datalength')})"
    ft = "INS=?"

    # + BACkTEST
    if cvars.get("datatype") == "backtest":
        metadatafile = f""
        metadatafile = f"{cvars.get('datadir')}/{cvars.get('backtestmeta')}"
        metadata = cvars.cload(metadatafile)
        # + atype = metadata['type']
        atype = g.datasetname
        pair = metadata['pair']
        timeframe = metadata['t_frame']
        count = metadata['count']
        exchange = metadata['exchange']
        # + fromdate = metadata['fromdate']
        fromdate = state_r("from")
        # + todate = metadata['todate']
        todate = state_r("to")

        deltadays = days_between(fromdate.replace("_", " "), todate)
        state_wr("delta_days", f"{deltadays}")
        ft = f"INS={g.instance_num}/{g.wordlabel} ({deltadays})[{atype}] {pair} {timeframe} {livect} FROM:{fromdate}  TO:{todate}"

    # + LIVE
    if cvars.get("datatype") == "live":
        atype = "LIVE"
        count = "N/A"
        exchange = "Binance"
        fromdate = "Ticker"
        todate = "Live"
        deltadays = days_between(fromdate, todate)

        ft = f"INS={g.instance_num}/{g.wordlabel} ({deltadays})[{atype}] {pair} {timeframe} FROM:{fromdate}  TO:{todate}"

    # + RANDOM
    if cvars.get("datatype") == "random":
        atype = "Random"
        count = "N/A"
        exchange = "N/A"
        fromdate = "N/A"
        todate = "N/A"
        deltadays = days_between(fromdate, todate)

        ft = f"INS={g.instance_num}/{g.wordlabel} {livect} pts:{count}"

    # + g.subtot_cost, g.subtot_qty, g.avg_price = itemgetter(0, 1, 2)(list_avg(state_r('open_buys'),state_r('qty_holding')))
    # + g.subtot_qty = trunc(g.subtot_qty)
    # + g.subtot_cost = trunc(g.subtot_cost)

    g.pnl_running = truncate(state_r('pnl_running'), 5)
    g.pct_running = truncate(state_r('pct_running'), 5)

    rpt = f" {g.subtot_qty} @ ${g.subtot_cost} !! ${g.pnl_running} /xx {g.pct_running}% "

    ft = f"{ft} !! {rpt}"
    return ft


def getdbconn(**kwargs):
    host = "localhost"
    try:
        host = kwargs["host"]
    except:
        pass
    dbconn = mdb.connect(user="jmc", passwd="6kjahsijuhdxhgd", host=host, db="jmcap")
    cursor = dbconn.cursor()
    return dbconn, cursor


def updateLegend(ax, idx):
    an = ax[0]
    # + testfor = {
    # + "bb3avg": "3 BBs Avg"
    # + , "buy_test_1": "C XU delta lowwater"
    # + , "buy_test_2": "C XU BB3 Low Avg"
    # + , "buy_test_3": "C XU BB3 Med Avg"
    # + , "buy_test_4": "C < O"
    # + , "sell_test_1": "C XO delta highwater"
    # + , "sell_test_2": "C XO BB3 High Avg"
    # + , "sell_test_3": "C XU BB3 High Avg"
    # + , "sell_test_4": f"C > Avg Holdings * {cvars.get('sell_test_4')}"
    # + , "sell_test_5": f"C > O"
    # + }
    # + 
    # + for key in testfor:
    # + if cvars.get(key):
    # + an.append(mpatches.Patch(color=None, fill=False, label=testfor[key]))

    an.append(mpatches.Patch(color=None, fill=False, label="------------------"))

    return an


def get_latest_time(ohlc):
    return (ohlc.Date[int(len(ohlc.Date) - 1)])


def get_last_price(exchange, **kwargs):
    quiet = False
    try:
        quiet = kwargs['quiet']
    except:
        pass
    pair = cvars.get("price_conversion")
    if not quiet:
        log2file("Remote connecting...(fetching ticker price)...", "counter.log")
    g.last_conversion = g.conversion
    if cvars.get("convert_price"):                      # * are we choosing to see the price in dollars?
        if cvars.get("offline_price"):                  # * do we want tegh live (slow) price can we live with the fixed (fast) price?
            if not quiet:
                g.logit.info(f"Using fixed conversion rate: {g.conversion}")
            return cvars.get("offline_price")           # * if so, retuirn fixed price
    try:                                                # * otherwsie, get the live price
        g.conversion = exchange.fetch_ticker(pair)['last']
        if not quiet:
            g.logit.info(f"Latest conversion rate: {g.conversion}")
        return g.conversion
    except:                                             # * which sometimes craps out
        g.logit.critical("Can't get price from Coinbase.  Check connection?")
        return g.last_conversion                        # * in which case, use last good value


def truncate(number, digits) -> float:
    stepper = 10.0 ** digits
    try:
        return math.trunc(stepper * number) / stepper
    except:
        return 0


def wavg(shares, prices):
    numer = 0
    denom = 0
    for i in range(len(shares)):
        numer = numer + (prices[i] * shares[i])
        denom = denom + shares[i]
    try:
        avg = numer / denom
    except:
        avg = numer
    return numer, denom, avg


def get_secret(**kwargs):
    exchange = kwargs['provider']
    apitype = kwargs['apitype']
    # + item = kwargs['item']

    with open("/home/jw/.secrets/keys.json") as json_file:
        data = json.load(json_file)

    return data[exchange][apitype]


def tryif(src, idx, fallback):
    try:
        rs = src[idx]
    except:
        rs = fallback

    return (rs)


def eprint(*args, **kwargs):
    print(Fore.RED + "!", *args, file=sys.stderr, **kwargs)
    cclr()


def oprint(*args, **kwargs):
    g.logit.debug(*args, **kwargs, extra={'mod_name': 'lib_olhc'})

    # + pd = pp.pformat(*args, indent=4, width=1)
    # + eprint(pd)

    eprint(*args, **kwargs)
    sys.stdout.flush()
    print(*args, file=sys.stdout, **kwargs)


# + -------------------------------------------------------------
# +  MODIFIERS
# + -------------------------------------------------------------

def normalize_col(acol, newmin=0.0, newmax=1.0):
    amin = acol.min()
    amax = acol.max()
    # + acol = ((acol-amin)/(amax-amin))*newmax
    acol = ((acol - amin) / (amax - amin)) * (newmax - newmin) + newmin
    return acol


def normalize_col_df(df, column, newmin=0, newmax=1):
    # + df[column] = (df[column] - df[column].min()) / (df[column].max() - df[column].min())
    df[column] = ((df[column] - df[column].min())) / (df[column].max() - df[column].min()) * (newmax - newmin) + newmin
    return df


# + -------------------------------------------------------------
# +  DATA & GENERATED DATA
# + -------------------------------------------------------------

# + - ADDS - mainly used just for BB3 and BBAVG, # + 1 and # + 2

def add_bolbands(ohlc, **kwargs):
    ax = kwargs['ax']

    bb = []
    bblengths = cvars.get("bblengths")
    bbc = len(bblengths)  # + how many BB windows will we average?
    bbstd = cvars.get("bbstd")
    for i in range(bbc):
        # + just look at the closing price
        bb.append(ta.bbands(close=ohlc[cvars.get("BBbasis")], length=bblengths[i], std=bbstd[i]))
    # + average
    bbu_avg = []
    bbl_avg = []
    bbm_avg = []
    # + generat average cols
    for k in range(len(bb[0])):
        upper = 0
        lower = 0
        for i in range(bbc):
            upper = upper + bb[i][f'BBU_{bblengths[i]}_{bbstd[i]}'][k]
            lower = lower + bb[i][f'BBL_{bblengths[i]}_{bbstd[i]}'][k]
        bbu_avg.append(upper / 3)
        bbl_avg.append(lower / 3)
        bbm_avg.append(((upper / 3) + (lower / 3)) / 2)

    # + add to df
    ohlc["bbuAvg"] = bbu_avg
    ohlc["bblAvg"] = bbl_avg
    ohlc["bbmAvg"] = bbm_avg

    # + appliea EWM to ONLY the BB-AVG, NOY the individual BB plots
    if cvars.get("bbavg_ewm"):
        ohlc.bbuAvg = ohlc.bbuAvg.ewm(span=cvars.get("bb_ewm_length")["upper"], adjust=False).mean()
        ohlc.bbmAvg = ohlc.bbmAvg.ewm(span=cvars.get("bb_ewm_length")["middle"], adjust=False).mean()
        ohlc.bblAvg = ohlc.bblAvg.ewm(span=cvars.get("bb_ewm_length")["lower"], adjust=False).mean()

    # + create the colums for the standard BB for each width
    for i in range(bbc):
        ohlc[f'bbh{i}'] = bb[i][f'BBU_{bblengths[i]}_{bbstd[i]}']  # + .bollinger_hband_indicator()
        ohlc[f'bbl{i}'] = bb[i][f'BBL_{bblengths[i]}_{bbstd[i]}']  # + .bollinger_lband_indicator()
        # + can't fill in mplfinance subplots :(
        # + ax.fill_between(ohlc['Date'], ohlc[f"bbh{i}"], ohlc[f"bbl{i}"])

    return ohlc


def add_2_bolbands(ohlc, **kwargs):
    ax = kwargs['ax']

    bb = []
    bblengths = cvars.get("bb2lengths")
    bbc = len(bblengths)  # + how many BB windows will we average?
    bbstd = cvars.get("bb2std")
    for i in range(bbc):
        try:  # + * first array after normalizqationis all NaN's, so use Close untilk there is data
            bb.append(ta.bbands(close=ohlc[cvars.get("BB2basis")], length=bblengths[i], std=bbstd[i]))
        except:
            bb.append(ta.bbands(close=ohlc['Close'], length=bblengths[i], std=bbstd[i]))
    # + average
    bbu_avg = []
    bbl_avg = []
    bbm_avg = []
    # + generat average cols
    for k in range(len(bb[0])):
        upper = 0
        lower = 0
        for i in range(bbc):
            upper = upper + bb[i][f'BBU_{bblengths[i]}_{bbstd[i]}'][k]
            lower = lower + bb[i][f'BBL_{bblengths[i]}_{bbstd[i]}'][k]
        bbu_avg.append(upper / 3)
        bbl_avg.append(lower / 3)
        bbm_avg.append(((upper / 3) + (lower / 3)) / 2)

    # + add to df
    ohlc["bbu2Avg"] = bbu_avg
    ohlc["bbl2Avg"] = bbl_avg
    ohlc["bbm2Avg"] = bbm_avg

    # + appliea EWM to ONLY the BB-AVG, NOY the individual BB plots
    if cvars.get("bbavg_ewm"):
        ohlc['bbu2Avg'] = ohlc['bbu2Avg'].ewm(span=cvars.get("bb_ewm_length")["upper"], adjust=False).mean()
        ohlc['bbm2Avg'] = ohlc['bbm2Avg'].ewm(span=cvars.get("bb_ewm_length")["middle"], adjust=False).mean()
        ohlc['bbl2Avg'] = ohlc['bbl2Avg'].ewm(span=cvars.get("bb_ewm_length")["lower"], adjust=False).mean()

    # + create the colums for the standard BB for each width
    for i in range(bbc):
        ohlc[f'bb2h{i}'] = bb[i][f'BBU_{bblengths[i]}_{bbstd[i]}']  # + .bollinger_hband_indicator()
        ohlc[f'bb2l{i}'] = bb[i][f'BBL_{bblengths[i]}_{bbstd[i]}']  # + .bollinger_lband_indicator()
        # + can't fill in mplfinance subplots :(
        # + ax.fill_between(ohlc['Date'], ohlc[f"bbh{i}"], ohlc[f"bbl{i}"])

    return ohlc


def add_bbl_plots(ohlc, **kwargs):
    ax = kwargs['ax']
    band = kwargs['band'] - 1
    # + create array to hold the hi/lo for each bb in a df for each width
    bblo = [False]
    bbhi = [False]

    thisband = f"bb{band + 1}style"

    color = cvars.get(thisband)["color"]
    width = cvars.get(thisband)['width']
    alpha = cvars.get(thisband)['alpha']
    bblo = mpf.make_addplot(ohlc[f'bbl{band}'], ax=ax, color=color, width=width, alpha=alpha)
    bbhi = mpf.make_addplot(ohlc[f'bbh{band}'], ax=ax, color=color, width=width, alpha=alpha)

    # + ohlc['xax'] = pd.to_datetime(ohlc['Date'], format='%Y-%m-%d %H:%M:%S.%f')
    # + g.logit.debug(ohlc.info())
    # + ohlc.set_index(['xax'], inplace=True)
    # + d = ohlc['Date']
    # + d = ohlc['Date'].dt.to_pydatetime()

    # + if cvars.get("fill"):
    # + # + d = ohlc['Date'].dt.to_pydatetime()
    # + # + ax.fill_between(ohlc.index,ohlc[f'bbl{band}'],ohlc[f'bbl{band}'],  facecolor='blue', alpha=0.2)
    return [bblo, bbhi]


def add_2_bbl_plots(ohlc, **kwargs):
    ax = kwargs['ax']
    band = kwargs['band'] - 1
    # + create array to hold the hi/lo for each bb in a df for each width
    bblo = [False]
    bbhi = [False]

    thisband = f"bb2{band + 1}style"

    color = cvars.get(thisband)["color"]
    width = cvars.get(thisband)['width']
    alpha = cvars.get(thisband)['alpha']

    bblo = mpf.make_addplot(ohlc[f'bb2l{band}'], ax=ax, color=color, width=width, alpha=alpha)
    bbhi = mpf.make_addplot(ohlc[f'bb2h{band}'], ax=ax, color=color, width=width, alpha=alpha)

    return [bblo, bbhi]


def add_bb_avg_plots(ohlc, **kwargs):
    ax = kwargs['ax']
    bbl_avg = mpf.make_addplot(ohlc['bblAvg'], ax=ax, color=cvars.get('bblAvgstyle')["color"],
                               width=cvars.get('bblAvgstyle')["width"], alpha=cvars.get('bblAvgstyle')["alpha"])
    bbm_avg = mpf.make_addplot(ohlc['bbmAvg'], ax=ax, color=cvars.get('bbmAvgstyle')["color"],
                               width=cvars.get('bbmAvgstyle')["width"], alpha=cvars.get('bbmAvgstyle')["alpha"])
    bbu_avg = mpf.make_addplot(ohlc['bbuAvg'], ax=ax, color=cvars.get('bbuAvgstyle')["color"],
                               width=cvars.get('bbuAvgstyle')["width"], alpha=cvars.get('bbuAvgstyle')["alpha"])
    return [bbl_avg, bbm_avg, bbu_avg]


def add_2_bb_avg_plots(ohlc, **kwargs):
    ax = kwargs['ax']
    bbl_avg = mpf.make_addplot(ohlc['bbl2Avg'], ax=ax, color=cvars.get('bbl2Avgstyle')["color"],
                               width=cvars.get('bbl2Avgstyle')["width"], alpha=cvars.get('bbl2Avgstyle')["alpha"])
    bbm_avg = mpf.make_addplot(ohlc['bbm2Avg'], ax=ax, color=cvars.get('bbm2Avgstyle')["color"],
                               width=cvars.get('bbm2Avgstyle')["width"], alpha=cvars.get('bbm2Avgstyle')["alpha"])
    bbu_avg = mpf.make_addplot(ohlc['bbu2Avg'], ax=ax, color=cvars.get('bbu2Avgstyle')["color"],
                               width=cvars.get('bbu2Avgstyle')["width"], alpha=cvars.get('bbu2Avgstyle')["alpha"])
    return [bbl_avg, bbm_avg, bbu_avg]


# + - GETS

def get_ohlc(ticker_src, spot_src, **kwargs):
    pair = cvars.get("pair")
    timeframe = cvars.get("timeframe")
    since = kwargs['since']
    normalize = cvars.get("normalize")

    pup = cvars.get("spread") + 1
    pdn = 1 - cvars.get("spread")

    def tfunc(df, col, **kwargs):
        try:
            final = kwargs['final']
        except:
            final = False
        # + global g.idx
        rs = 100
        alter = cvars.get("modby")
        if col == "Open":
            rs = random.uniform(df['Close'] * pdn, df['Close'] * pup)
            rs = alter(rs, g.idx) if alter else rs
        if col == "High":
            rs = random.uniform(df['Close'], df['Close'] * pup)
            rs = alter(rs, g.idx) if alter else rs
        if col == "Low":
            rs = random.uniform(df['Close'], df['Close'] * pdn)
            rs = alter(rs, g.idx) if alter else rs
        if col == "Close":
            if final:
                rs = random.uniform(df['Low'], df['High'])
            else:
                rs = random.uniform(df['Close'] * pdn, df['Close'] * pup)
                rs = alter(rs, g.idx) if alter else rs
        if col == "Volume":
            rs = random.uniform(0, 100)
        g.idx = g.idx + 1
        return (rs)

    def alter(x, n):
        lo = x
        hi = x
        if (n % cvars.get('modby')[0]) > cvars.get('modby')[1]:
            lo = x * (1 - cvars.get('modby')[2])
            hi = x * (1 + cvars.get('modby')[2])
        x = random.uniform(lo, hi)
        return (x)

    epoch_ms = 1634277300000  # + ! arbitrary.. just need some epoch date when makign randomdata
    data = []

    # + * -------------------------------------------------------------
    # + *  RANDOM DATA
    # + * -------------------------------------------------------------
    if cvars.get("datatype") == "random":
        g.datawindow = g.datawindow - 1  # + ! for some reason, 'live' and 'random' require 'datawindow-1' to work, but 'backtest' needs 'datawindow'
        columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
        d = {}
        for k in range(g.datawindow):
            data.append({"Timestamp": float("Nan"), "Open": float("Nan"), "High": float("Nan"), "Low": float("Nan"),
                         "Close": float("Nan"), "Volume": float("Nan")})
        for k in range(g.datawindow):
            data[k]['Timestamp'] = epoch_ms
            epoch_ms = epoch_ms + cvars.get("epoch_ms_delta")

        df = pd.DataFrame(data)
        df.set_index("Timestamp")

        seed = cvars.get("seed")
        mu = cvars.get("mu")
        sigma = cvars.get("sigma")
        np.random.seed(seed)
        returns = np.random.normal(loc=mu, scale=sigma, size=g.datawindow)
        ary = 5 * (1 + returns).cumprod()
        df["Close"] = ary

        for c in ["Open", "High", "Low", "Close", "Volume"]:
            g.idx = 0
            df[c] = df.apply(lambda x: tfunc(x, c), axis=1)
        g.idx = 0
        df['Close'] = df.apply(lambda x: tfunc(x, "Close", final=True), axis=1)

        df['orgClose'] = df['Close']
        df["Date"] = pd.to_datetime(df.Timestamp, unit='ms')
        df.index = pd.DatetimeIndex(df['Timestamp'])

        ohlc = df.loc[:, ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'orgClose']]
        ohlc['ID'] = range(len(df))
        ohlc["Date"] = pd.to_datetime(ohlc.Timestamp, unit='ms')
        ohlc.index = pd.DatetimeIndex(df['Timestamp'])

    # + * -------------------------------------------------------------
    # + *  LIVE DATA
    # + * -------------------------------------------------------------
    if cvars.get("datatype") == "live":
        # + ! datawindow = datawindow - 1 # + index mismatch.  expecting 70, got 71
        # + !                             index mismatch.  expecting 72, got 71)
        log2file("Remote connecting (fetching OHLC...)","counter.log")
        # + LOAD
        ohlcv = ticker_src.fetch_ohlcv(symbol=pair, timeframe=timeframe, since=since, limit=g.datawindow)

        df = pd.DataFrame(ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['orgClose'] = df['Close']
        df["Date"] = pd.to_datetime(df.Timestamp, unit='ms')
        df.index = pd.DatetimeIndex(df['Timestamp'])
        ohlc = df.loc[:, ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'orgClose']]
        ohlc['ID'] = range(len(df))
        ohlc["Date"] = pd.to_datetime(ohlc.Timestamp, unit='ms')
        # + ohlc.index = pd.DatetimeIndex(df['Timestamp'])
        ohlc.index = ohlc['Date']

    # + * -------------------------------------------------------------
    # + *  BACKTEST DATA
    # + * -------------------------------------------------------------
    if cvars.get("datatype") == "backtest":
        datafile = f"{cvars.get('datadir')}/{cvars.get('backtestfile')}"
        df = cvars.load(datafile, maxitems=cvars.get("datalength"))

        df.rename(columns={'Date': 'Timestamp'}, inplace=True)
        df['orgClose'] = df['Close']

        if cvars.get("startdate"):
            # + * calculate new CURRENT time, not starting time of chart
            old_start_time = df.iloc[0]['Timestamp']
            new_start_time = df.iloc[0]['Timestamp'] + dt.timedelta(minutes=5 * g.datawindow)
            print("old/new start time:", old_start_time, new_start_time)
            date_mask = (df['Timestamp'] > new_start_time)
            df = df.loc[date_mask]

        df["Date"] = pd.to_datetime(df['Timestamp'], unit='ms')
        df.index = pd.DatetimeIndex(df['Timestamp'])

        _start = (g.datawindow) + g.gcounter
        _end = _start + (g.datawindow)

        ohlc = df.iloc[_start:_end]

        # + ! copying a df generated complained that I am trying to modiofy a copy, so this is to create
        # + ! a copy that has no record that it si a copy. tmp fix, find a better way
        fn = f"_tmp1_{g.instance_num}.json"
        cvars.save(ohlc, fn)
        ohlc = cvars.load(fn)
        os.remove(fn)
        ohlc['ID'] = range(len(ohlc))

    # * data loaded
    # * check to see if the price has changed
    g.this_close = ohlc['Close'][-1]
    if g.this_close != g.last_close:
        log2file("Price change","counter.log")
        os.system(f"aplay assets/laser.wav > /dev/null 2>&1")
    g.last_close = g.this_close

    # * save last Close valuie

    ohlc.Open = ohlc.Open.apply(lambda x: x * g.conversion)
    ohlc.High = ohlc.High.apply(lambda x: x * g.conversion)
    ohlc.Low = ohlc.Low.apply(lambda x: x * g.conversion)
    ohlc.Close = ohlc.Close.apply(lambda x: x * g.conversion)

    if normalize:
        ohlc.Open = normalize_col(ohlc.Open)
        ohlc.Low = normalize_col(ohlc.Low)
        ohlc.High = normalize_col(ohlc.High)
        ohlc.Close = normalize_col(ohlc.Close)

    dto = f"{max(ohlc['Timestamp'])}"  # + * get latest time
    if not state_r("from"):
        state_wr("from", f"{dto}")
    state_wr("last_seen_date", f"{dto}")
    g.can_load = False
    return ohlc

def log2file(data,filename):
    file1 = open(f"logs/{filename}","a")
    file1.write(data+"\n")
    file1.close()

def get_opcldelta(df, **kwargs):
    ax = kwargs['ax']

    def _inter(x):
        return tfunc(x['Open'], x['Close'])

    def tfunc(open, close):
        return close - open

    df["opcldelta"] = float("Nan")
    df['opcldelta'] = df.apply(_inter, axis=1)
    amin = df['Volume'].min()
    amax = df['Volume'].max()
    # + amin=df['Close'].min()
    # + amax=df['Close'].max()
    df['opcldelta'] = normalize_col(df.opcldelta, amin, amax)

    opcldelta_plot = [
        # + df.opcldelta.ewm(span=5, adjust=False).mean(),
        mpf.make_addplot(
            df.opcldelta,
            ax=ax,
            scatter=False,
            color=cvars.get('opcldeltastyle')['color'],
            width=cvars.get('opcldeltastyle')['width'],
            alpha=cvars.get('opcldeltastyle')['alpha'],
        )
    ]
    return opcldelta_plot


def get_hilodelta(df, **kwargs):
    ax = kwargs['ax']

    def _inter(x):
        return tfunc(x['High'], x['Low'])

    def tfunc(high, low):
        return high - low

    df["hilodelta"] = float("Nan")
    df['hilodelta'] = df.apply(_inter, axis=1)
    amin = df['Volume'].min()
    amax = df['Volume'].max()
    # + amin=df['Close'].min()
    # + amax=df['Close'].max()
    df['hilodelta'] = normalize_col(df.hilodelta, amin, amax)

    hilodelta_plot = [
        # + df.hilodelta.ewm(span=5, adjust=False).mean(),
        mpf.make_addplot(
            df.hilodelta,
            ax=ax,
            scatter=False,
            color=cvars.get('hilodeltastyle')['color'],
            width=cvars.get('hilodeltastyle')['width'],
            alpha=cvars.get('hilodeltastyle')['alpha'],
        ),
    ]
    return hilodelta_plot


def get_macdema(df, **kwargs):
    ax = kwargs['ax']
    MACD_src = cvars.get('MACD_src')
    EMA_fast = cvars.get('EMA_fast')
    EMA_slow = cvars.get('EMA_slow')
    signal_span = cvars.get('signal_span')

    df["macd"] = float("Nan")
    df["macd_signal"] = float("Nan")
    df["macd_hist"] = float("Nan")

    # df["MACD"], df["MACDSignalLine"], df["Histogram"] = ta.macd(df['Close'])

    df[f'EMA{EMA_fast}'] = df[MACD_src].ewm(span=EMA_fast).mean()
    df[f'EMA{EMA_slow}'] = df[MACD_src].ewm(span=EMA_slow).mean()

    # + * there are cases when we want the EMA but now show it (ex, MACD), so if teh 'plots_ame_hide' is on,
    # + * just retirn False

    if cvars.get('plots_ema_hide'):
        macdema_plot = False
    else:
        macdema_plot = [
            mpf.make_addplot(df[f'EMA{EMA_fast}'], ax=ax, color=cvars.get('EMA_1style')['color']),
            mpf.make_addplot(df[f'EMA{EMA_slow}'], ax=ax, color=cvars.get('EMA_2style')['color']),
        ]
    return macdema_plot


def get_macd(df, **kwargs):
    ax = kwargs['ax']

    MACD_src = cvars.get('MACD_src')
    EMA_fast = cvars.get('EMA_fast')
    EMA_slow = cvars.get('EMA_slow')
    signal_span = cvars.get('signal_span')

    df["macd"] = float("Nan")
    df["macd_signal"] = float("Nan")
    df["macd_hist"] = float("Nan")

    df[f'EMA{EMA_fast}'] = df[MACD_src].ewm(span=EMA_fast).mean()
    df[f'EMA{EMA_slow}'] = df[MACD_src].ewm(span=EMA_slow).mean()

    # ! using pandas_ta crashed ONLU on debian,.  talib works
    # !df["MACD"], df["MACDSignalLine"], df["Histogram"] = ta.macd[MACD_src]
    df["MACD"], df["MACDSignalLine"], df["Histogram"] = talib.MACD(df[MACD_src])

    df['MACD'] = df['EMA12'] - df['EMA26']
    df['MACDSignalLine'] = df['MACD'].ewm(span=signal_span).mean()
    df['Histogram'] = df['MACD'] - df['MACDSignalLine']
    macd_plot = [
        mpf.make_addplot(df['MACD'], ax=ax, secondary_y=True, color=cvars.get('MACDstyle')['color']),
        mpf.make_addplot(df['MACDSignalLine'], ax=ax, secondary_y=True, color=cvars.get('siglinstyle')['color']),
        mpf.make_addplot(df['Histogram'], ax=ax, secondary_y=False, color=cvars.get('histogramstyle')['color'],
                         type='bar')
    ]
    return macd_plot


def get_deltadelta(df, **kwargs):
    ax = kwargs['ax']

    def _inter(x):
        return tfunc(x['opcldelta'], x['hilodelta'])

    def tfunc(ocd, hld):
        return hld - ocd

    df["deltadelta"] = float("Nan")
    df['deltadelta'] = df.apply(_inter, axis=1)
    # + amin=df['Volume'].min()
    # + amax=df['Volume'].max()
    df['deltadelta'] = normalize_col(df.opcldelta)
    df['deltadelta'] = df['deltadelta'].apply(lambda x: x - 0.5)

    deltadelta_plot = [
        mpf.make_addplot(
            df.deltadelta,
            ax=ax,
            color=cvars.get('deltadeltastyle')['color'],
            width=cvars.get('deltadeltastyle')['width'],
            alpha=cvars.get('deltadeltastyle')['alpha'],
        )
    ]
    return deltadelta_plot


def get_volume(df, **kwargs):
    ax = kwargs['ax']
    type = kwargs['type']

    def tfunc(df, **kwargs):
        dir = kwargs['dir']
        # + rem neg
        if dir == "up":
            return df['Volume'] if df['Open'] < df['Close'] else float("Nan")
        if dir == "dn":
            return df['Volume'] if df['Open'] > df['Close'] else float("Nan")

    df['VolUp'] = df.apply(lambda x: tfunc(x, dir="up"), axis=1)
    df['VolDn'] = df.apply(lambda x: tfunc(x, dir="dn"), axis=1)
    varup_plot = mpf.make_addplot(
        df.VolUp,
        ax=ax,
        type=type,
        color=cvars.get('volclrupstyle')['color'],
        width=cvars.get('volclrupstyle')['width'],
        alpha=cvars.get('volclrupstyle')['alpha'],
    )
    vardn_plot = mpf.make_addplot(
        df.VolDn,
        ax=ax,
        type=type,
        color=cvars.get('volclrdnstyle')['color'],
        width=cvars.get('volclrdnstyle')['width'],
        alpha=cvars.get('volclrdnstyle')['alpha'],
    )
    return [varup_plot, vardn_plot]


# + 
def get_volume_line(df, **kwargs):
    ax = kwargs['ax']
    type = kwargs['type']
    df['voldelta'] = df['Volume']
    # + ! Volume represents the actual material in play, the 'amperage', so to speak, of the exchange
    # + ! The open/close delta represents the

    # + df['voldelta'] = df['Volume'] - (df['High'] - df['Low'])
    df['voldelta'] = df['Volume'] - (df['Close'] - df['Open'])
    df['voldelta'] = df['voldelta'].ewm(span=cvars.get('volumeline_span')).mean()

    vlines_plot = mpf.make_addplot(
        df['voldelta'],
        ax=ax,
        type=type,
        color=cvars.get('volclrupstyle')['color'],
        width=cvars.get('volclrupstyle')['width'],
        alpha=cvars.get('volclrupstyle')['alpha'],
    )

    # + ax.axhline(y=0.0, color="black")
    return [vlines_plot]


# + 
def get_tholo(df, **kwargs):
    ax = kwargs['ax']

    def tfunc(df):
        try:
            return df['hilodelta'] / df['Volume']
        except:
            return 0

    df["I"] = ((df['Volume'] - df['Volume'].min())) / (df['Volume'].max() - df['Volume'].min())  # + * (1 - 0) + 0
    df["V"] = ((df['hilodelta'] - df['hilodelta'].min())) / (
            df['hilodelta'].max() - df['hilodelta'].min())  # + * (1 - 0) + 0
    df['R'] = df.apply(lambda x: tfunc(x), axis=1)
    df["R"] = df['R'] = ((df['R'] - df['R'].min())) / (df['R'].max() - df['R'].min())  # + * (1 - 0) + 1
    df["S"] = ((df['Close'] - df['Close'].min())) / (df['Close'].max() - df['Close'].min())  # + * (1 - 0) + 0

    # + df["S"] = df["S"].ewm(span=cvars.get('tholo_span')).mean()
    df["V"] = df["V"].ewm(span=cvars.get('tholo_span')).mean()
    df["I"] = df["I"].ewm(span=cvars.get('tholo_span')).mean()
    df["R"] = df["R"].ewm(span=cvars.get('tholo_span')).mean()
    df["S"] = df["S"].ewm(span=cvars.get('tholo_span')).mean()

    df["V"] = normalize_col(df['V'], -0.5, 0.5)
    df["I"] = normalize_col(df['I'], -0.5, 0.5)
    df["R"] = normalize_col(df['R'], -0.5, 0.5)
    df["S"] = normalize_col(df['S'], -0.5, 0.5)

    V_plot = mpf.make_addplot(
        df['V'],
        ax=ax,
        type="line",
        color=cvars.get('tholostyle_V')['color'],
        width=cvars.get('tholostyle_V')['width'],
        alpha=cvars.get('tholostyle_V')['alpha'],
    )
    I_plot = mpf.make_addplot(
        df['I'],
        ax=ax,
        type="line",
        color=cvars.get('tholostyle_I')['color'],
        width=cvars.get('tholostyle_I')['width'],
        alpha=cvars.get('tholostyle_I')['alpha'],
    )
    R_plot = mpf.make_addplot(
        df['R'],
        ax=ax,
        type="line",
        color=cvars.get('tholostyle_R')['color'],
        width=cvars.get('tholostyle_R')['width'],
        alpha=cvars.get('tholostyle_R')['alpha'],
    )
    S_plot = mpf.make_addplot(
        df['S'],
        ax=ax,
        type="line",
        color=cvars.get('tholostyle_S')['color'],
        width=cvars.get('tholostyle_S')['width'],
        alpha=cvars.get('tholostyle_S')['alpha'],
    )
    return [V_plot, I_plot, R_plot, S_plot]

    # + return [V_plot, I_plot, R_plot]


def get_overunder(df, **kwargs):
    ax = kwargs['ax']

    def tfunc(df, **kwargs):
        field = kwargs['col']
        return df['Close'] - df[field]

    df['ou-mid'] = df.apply(lambda x: tfunc(x, col='bbmAvg'), axis=1)
    df['ou-mid'] = ta.sma(df['ou-mid'], length=6)
    df['ou-mid'] = normalize_col(df['ou-mid'], -0.5, 0.5)

    oum_plot = mpf.make_addplot(
        df['ou-mid'],
        ax=ax,
        type="line",
        color=cvars.get('overunder2style')['color'],
        width=cvars.get('overunder2style')['width'],
        alpha=cvars.get('overunder2style')['alpha'],
    )
    ax.axhline(y=cvars.get('overunder_sell'), color='cyan')
    ax.axhline(y=cvars.get('overunder_buy'), color='magenta')
    ax.axhline(y=0.0, color='black')

    return [oum_plot]


def get_pnl(ohlc, **kwargs):
    ax = kwargs['ax']

    plot_pnl = mpf.make_addplot(
        g.df_buysell['pnl'].iloc[::-1],
        ax=ax,
        type="line",
        color=cvars.get('tholostyle_I')['color'],
    )
    plot_pct = mpf.make_addplot(
        g.df_buysell['pct'].iloc[::-1],
        ax=ax,
        type="line",
        color=cvars.get('tholostyle_V')['color'],
    )
    return [plot_pnl, plot_pct]


def get_pct(ohlc, **kwargs):
    ax = kwargs['ax']
    tmp = g.df_buysell.iloc[::-1]
    plot_pct = mpf.make_addplot(
        tmp['pct'],
        ax=ax,
        type="line",
        color="green",
        width=2,
        alpha=1
    )
    return [plot_pct]


def get_pt1(ohlc, **kwargs):
    ax = kwargs['ax']
    # + * add the column
    ohlc['one_pt'] = 0

    def tfunc(dfline, **kwargs):
        df = kwargs['df']
        g.idx = dfline['ID']
        CLOSE = dfline['Close']
        OPEN = dfline['Open']
        g.pt1 = 0
        try:
            PCLOSE = df['Close'][g.idx - 1]
        except:
            PCLOSE = CLOSE

        if CLOSE > PCLOSE:
            g.pt1 = g.previous_point + 1
        if CLOSE < PCLOSE:
            g.pt1 = g.previous_point - 1

        g.previous_point = g.pt1
        return g.pt1

    ohlc['one_pt'] = ohlc.apply(lambda x: tfunc(x, df=ohlc, ax=ax), axis=1)

    ohlc['one_pt'] = ohlc['one_pt'].ewm(span=cvars.get("bb_ewm_length")["upper"], adjust=False).mean()

    ohlc['one_pt'] = normalize_col(ohlc['one_pt'], -0.5, 0.5)

    plot_pt1 = mpf.make_addplot(
        ohlc['one_pt'],
        ax=ax,
        type="line",
        color=cvars.get("pt1style")['color'],
        width=cvars.get("pt1style")['width'],
        alpha=1  # + cvars.get('tholostyle_I')['color'],
    )
    ax.axhline(y=0.0, color='black')
    ax.axhline(y=cvars.get("pt1_highlimit_sell"), color='cyan')
    ax.axhline(y=cvars.get("pt1_lowlimit_buy"), color='magenta')

    return [plot_pt1]


def get_normclose(ohlc, **kwargs):
    ax = kwargs['ax']
    # + * add the column
    ohlc['normclose'] = 0
    ohlc['normvol'] = 0

    ohlc['normclose'] = normalize_col(ohlc['Close'], -0.5, 0.5)
    ohlc['normvol'] = normalize_col(ohlc['Volume'], -0.5, 0.5)

    ohlc['normclose'] = (ohlc['normclose'] * ohlc['normvol'])
    # + ohlc['normclose'] = (ohlc['normclose'] - ohlc['one_pt']) * ohlc['Volume']
    # + ohlc['normclose'] =  (ohlc['one_pt'] - ohlc['normclose'])

    # + ohlc['normclose'] = ohlc['normclose'].ewm(span=cvars.get("bb_ewm_length")["upper"], adjust=False).mean()

    ohlc['normclose'] = normalize_col(ohlc['normclose'], -0.5, 0.5)

    plot_normclose = mpf.make_addplot(
        ohlc['normclose'],
        ax=ax,
        type="line",
        color=cvars.get("normclosestyle")['color'],
        width=cvars.get("normclosestyle")['width'],
        alpha=cvars.get('normclosestyle')['alpha'],
    )
    ax.axhline(y=0.0, color='black')
    # + ax.axhline(y=cvars.get("pt1_highlimit_sell"), color='cyan')
    # + ax.axhline(y=cvars.get("pt1_lowlimit_buy"), color='magenta')

    return [plot_normclose]


def get_sigff(df, **kwargs):
    ax = kwargs['ax']

    # + ! https://dsp.stackexchange.com/questions/19084/applying-filter-in-scipy-signal-use-lfilter-or-filtfilt

    # + * sigff: filtfilt is zero-phase filtering, which doesn't shift the signal as it filters.
    # + * Since the phase is zero at all frequencies, it is also linear-phase. Filtering backwards in
    # + * time requires you to predict the future, so it can't be used in "online" real-life applications,
    # + * only for offline processing of recordings of signals.

    def tfunc(dfline, **kwargs):
        df = kwargs['df']
        d = dfline['sigff']
        df = dfline['Close'] - d
        nclose = dfline['Close'] + (df * cvars.get('filter')["ffmx"])
        return nclose

    df['siglf'] = 0

    ftype = cvars.get('bw_filter')
    N = cvars.get('filter')[ftype]['N']
    Wn = cvars.get('filter')[ftype]['Wn']
    fname = cvars.get('filter')[ftype]['name']

    b, a = signal.butter(N, Wn, btype=fname, analog=False)
    sig = df['Close']
    sigff = signal.lfilter(b, a, signal.filtfilt(b, a, sig))

    g.bag['sigfft'].append(sigff[len(sigff) - 1])
    df['sigff'] = backfill(g.bag['sigfft'])
    df['sigff'] = df['Close'] + df['sigff']

    df['sigff'] = df.apply(lambda x: tfunc(x, df=df), axis=1)
    # + df['sigff'].ewm(span=6).mean()
    df['sigff'] = normalize_col(df['sigff'], -0.5, 0.5)

    plots_sigff_list = mpf.make_addplot(  # + * flatter
        df["sigff"],
        ax=ax,
        type="line",
        color=cvars.get("sigffstyle")['color'],
        width=cvars.get("sigffstyle")['width'],
        alpha=cvars.get('sigffstyle')['alpha'],
    )

    # + ax.set_ylim([-1,1])
    # + ax.axhline(y=0.0, color='black')
    # + ax.axhline(y=-0.5, color='magenta')
    # + ax.axhline(y=0.5, color='cyan')

    return [plots_sigff_list]


def get_siglf(df, **kwargs):
    ax = kwargs['ax']

    # + ! https://dsp.stackexchange.com/questions/19084/applying-filter-in-scipy-signal-use-lfilter-or-filtfilt

    # + * siglf: lfilter is causal forward-in-time filtering only, similar to a real-life electronic filter.
    # + * It can't be zero-phase. It can be linear-phase (symmetrical FIR), but usually isn't. Usually it adds
    # + * different amounts of delay at different frequencies.

    df['siglf'] = 0

    ftype = cvars.get('bw_filter')
    N = cvars.get('filter')[ftype]['N']
    Wn = cvars.get('filter')[ftype]['Wn']
    fname = cvars.get('filter')[ftype]['name']

    b, a = signal.butter(N, Wn, btype=fname, analog=False)
    sig = df['Close']
    siglf = signal.lfilter(b, a, signal.lfilter(b, a, sig))
    g.bag['siglft'].append(siglf[len(siglf) - 1])
    df['siglf'] = backfill(g.bag['siglft'])

    # + df['siglf'] =  df['Close'] + (df['siglf'] # + * cvars.get('filter')["lfmx"])
    df['siglf'] = df['siglf'] * cvars.get('filter')["lfmx"]
    df['siglf'] = normalize_col(df['siglf'], -0.5, 0.5)
    plots_siglf_list = mpf.make_addplot(  # + * flatter
        df["siglf"],
        ax=ax,
        type="line",
        color=cvars.get("siglfstyle")['color'],
        width=cvars.get("siglfstyle")['width'],
        alpha=cvars.get('siglfstyle')['alpha'],
    )
    # + ax.axhline(y=0.0, color='black')
    # + ax.axhline(y=-5, color='magenta')
    # + ax.axhline(y=5, color='cyan')

    return [plots_siglf_list]


def get_sigffmb(df, **kwargs):
    ax = kwargs['ax']
    band = kwargs['band']
    N = kwargs['N']
    Wn = kwargs['Wn']

    def tfunc(dfline, **kwargs):
        df = kwargs['df']
        band = kwargs['band']

        d = dfline[f'sigffmb{band}']  # + * the sig value, can be very small
        df = dfline['Close'] - d

        nclose = dfline['Close']  # + (df*cvars.get('mbpfilter')["mx"][band])

        return nclose

    colname = f'sigffmb{band}'
    df[colname] = 0

    b, a = signal.butter(N, Wn, btype="bandpass", analog=False)  # + * get filter params
    sig = df['Close']  # + * select data to filter
    sigff = signal.lfilter(b, a, signal.filtfilt(b, a, sig))  # + * get the filter
    g.bag[f'sigfft{band}'].append(sigff[len(sigff) - 1])  # + * store results in temp location
    df[colname] = backfill(g.bag[f'sigfft{band}'])  # + * fill data to match df shape
    # + df[colname] = df['Close'] + df[colname]                      # + * add sig data to close

    # + df[colname] = df.apply(lambda x:tfunc(x,band=band,df=df),axis=1) # + !JWXXX

    plots_sigffmb_list = mpf.make_addplot(  # + * flatter
        df[colname],
        ax=ax,
        type="line",
        color=cvars.get("sigffmbstyle")['color'][band],
        width=cvars.get("sigffmbstyle")['width'],
        alpha=cvars.get('sigffmbstyle')['alpha'],
    )

    return [plots_sigffmb_list]


def get_sigffmb2(df, **kwargs):
    ax = kwargs['ax']
    band = kwargs['band']
    N = kwargs['N']
    Wn = kwargs['Wn']

    def tfunc(dfline, **kwargs):
        df = kwargs['df']
        band = kwargs['band']
        d = dfline[f'sigffmb2{band}']
        df = dfline['rohlc'] - d
        nclose = dfline['rohlc']  # + (df*cvars.get('mbpfilter')["mx"][band])
        return nclose

    colname = f'sigffmb2{band}'
    df[colname] = 0

    b, a = signal.butter(N, Wn, btype="bandpass", analog=False)
    sig = df['rohlc']
    sigff = signal.lfilter(b, a, signal.filtfilt(b, a, sig))
    g.bag[f'sigfft2{band}'].append(
        sigff[len(sigff) - 1])  # + ! g.bag[f'sigfft2{band}'] MUST be defined in lib_globals (for now)
    df[colname] = backfill(g.bag[f'sigfft2{band}'])
    # + df[colname] = df['rohlc'] + df[colname]

    # + df[colname] = df.apply(lambda x:tfunc(x,band=band,df=df),axis=1)
    # + df[colname].ewm(span=6).mean()

    plots_sigffmb2_list = mpf.make_addplot(  # + * flatter
        df[colname],
        ax=ax,
        type="line",
        color=cvars.get("sigffmb2style")['color'][band],
        width=cvars.get("sigffmb2style")['width'],
        alpha=cvars.get('sigffmb2style')['alpha'],
    )

    return [plots_sigffmb2_list]


# + - GEMERATOR UIILS

def backfill(collected_data, **kwargs):
    fillwith = None
    try:
        fillwith = kwargs['fill']
    except:
        pass

    newary = []
    _tmp = collected_data[::-1]
    # + for i in range(cvars.get('datawindow')):
    i = 0
    while len(newary) < g.datawindow:
        if i < len(_tmp):
            newary.append(_tmp[i])
        else:
            newary.append(fillwith)
        i = i + 1
    return newary[::-1]


def sqlex(cmd):
    g.logit.debug(f"SQL Command:{cmd}")
    try:
        g.cursor.execute("SET AUTOCOMMIT = 1")
        g.cursor.execute(cmd)
        g.dbc.commit()
        rs = g.cursor.fetchall()
    except Exception as ex:
        handleEx(ex, cmd)
        exit(1)

    return(rs)

def calcfees(rs_ary):
    fees = 0
    try:
        for fn in rs_ary['resp']:
            rrec = pd.read_pickle(fn)

            # + pp.pprint(rrec)
            fees = fees + float(rrec['fill_fees'])
    except:
        pass

    return fees


# + -------------------------------------------------------------
# +  PLOTS
# + -------------------------------------------------------------

def plots_macdema(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    EMA_fast = cvars.get('EMA_fast')
    EMA_slow = cvars.get('EMA_slow')

    plots_macdema_list = add_plots(plots, get_macdema(ohlc, ax=ax))

    if not cvars.get('plots_ema_hide'):
        patches.append(mpatches.Patch(color=cvars.get('EMA_1style')['color'], label=f"EMA{EMA_slow}"))
        patches.append(mpatches.Patch(color=cvars.get('EMA_2style')['color'], label=f"EMA{EMA_fast}"))

    return plots_macdema_list


def plots_macd(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_macd_list = add_plots(plots, get_macd(ohlc, ax=ax))

    patches.append(mpatches.Patch(color=cvars.get('MACDstyle')['color'], label="MACD"))
    patches.append(mpatches.Patch(color=cvars.get('siglinstyle')['color'], label="SignalLine"))
    patches.append(mpatches.Patch(color=cvars.get('histogramstyle')['color'], label="Histogram"))
    return plots_macd_list


def plots_tholo(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_macd_list = add_plots(plots, get_tholo(ohlc, ax=ax))

    patches.append(mpatches.Patch(color=cvars.get('tholostyle_V')['color'], label="V (hilo)"))
    patches.append(mpatches.Patch(color=cvars.get('tholostyle_I')['color'], label="I (vol)"))
    patches.append(mpatches.Patch(color=cvars.get('tholostyle_R')['color'], label="R ($)"))
    patches.append(mpatches.Patch(color=cvars.get('tholostyle_S')['color'], label="Close ($)"))
    return plots_macd_list


def plots_overunder(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_overunder_list = add_plots(plots, get_overunder(ohlc, ax=ax))

    patches.append(mpatches.Patch(color=cvars.get('overunderstyle')['color'], label="O/U"))
    return plots_overunder_list


def plots_pt1(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_pt1_list = add_plots(plots, get_pt1(ohlc, ax=ax))
    patches.append(mpatches.Patch(color=cvars.get('pt1style')['color'], label="1-pt"))

    return plots_pt1_list


def plots_normclose(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_normclose_list = add_plots(plots, get_normclose(ohlc, ax=ax))
    patches.append(mpatches.Patch(color=cvars.get('normclosestyle')['color'], label="Close (Norm)"))

    return plots_normclose_list


def plots_sigff(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_fft_list = add_plots(plots, get_sigff(ohlc, ax=ax))

    f = cvars.get("bw_filter")
    N = cvars.get("filter")[f]['N']
    Wn = cvars.get("filter")[f]['Wn']
    label = f"FF {f}({N},{Wn})"

    patches.append(mpatches.Patch(color=cvars.get('sigffstyle')['color'], label=label))
    return plots


def plots_siglf(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    f = cvars.get("bw_filter")
    N = cvars.get("filter")[f]['N']
    Wn = cvars.get("filter")[f]['Wn']
    label = f"FL(t) {f}({N},{Wn})"

    plots_fft_list = add_plots(plots, get_siglf(ohlc, ax=ax))
    patches.append(mpatches.Patch(color=cvars.get('siglfstyle')['color'], label=label))
    return plots


def plots_sigffmb(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    N = cvars.get("mbpfilter")['N']
    Wn_ary = cvars.get("mbpfilter")['Wn']

    if not cvars.get("plots_sigffmb_hide"):
        for j in range(len(Wn_ary)):
            plots = add_plots(plots, get_sigffmb(ohlc, N=N, Wn=Wn_ary[j], band=j, ax=ax))
            label = f"FFmap {N},{Wn_ary[j]})"
            patches.append(mpatches.Patch(color=cvars.get('sigffmbstyle')['color'][j], label=label))
    else:  # + * JUST GET THE DATA, DONT PLOT
        for j in range(len(Wn_ary)):
            get_sigffmb(ohlc, N=N, Wn=Wn_ary[j], band=j, ax=ax)

    # + * we now have all the bands in cols 'sigffmb<band number>'
    # + ohlc['ffmap'] = (ohlc['sigffmb2']**2) * cvars.get('mbpfilter')['mx'][2]

    for j in range(len(Wn_ary)):  # + !JWXXX
        ohlc[f'sigffmb{j}'] = normalize_col(ohlc[f'sigffmb{j}'])  # + * set all bands to teh same data range

    ohlc['ffmap'] = ohlc['sigffmb0']
    for j in range(len(Wn_ary[1:])):
        ohlc['ffmap'] = ohlc['ffmap'] + ohlc[f'sigffmb{j}']  # + * add them all together
    ohlc['ffmap'] = 1 / ohlc['ffmap']

    plots_sigffmap_list = mpf.make_addplot(
        ohlc['ffmap'],
        ax=ax,
        type="line",
        color=cvars.get("ffmapstyle")['color'],
        width=cvars.get("ffmapstyle")['width'],
        alpha=cvars.get('ffmapstyle')['alpha'],
    )

    patches.append(mpatches.Patch(color=cvars.get('ffmapstyle')['color'], label="OHLC(sum(6f)^2)"))

    amin = float(ohlc['ffmap'].min())
    amax = float(ohlc['ffmap'].max())

    # + delta = (amax-amin)/100 # + * 1%
    delta = (amax - amin) * (cvars.get('lowpctline') / 100)

    ax.axhline(amin + delta,
        color=cvars.get("ffmaplolimstyle")['color'],
        linewidth=cvars.get("ffmaplolimstyle")['linewidth'],
        alpha=cvars.get('ffmaplolimstyle')['alpha']
    )
    ax.axhline(amax - delta,
        color=cvars.get("ffmaphilimstyle")['color'],
        linewidth=cvars.get("ffmaphilimstyle")['linewidth'],
        alpha=cvars.get('ffmaphilimstyle')['alpha']
    )


    ohlc['ffmapllim'] = amin + delta
    ohlc['ffmapulim'] = amax - delta

    plots = add_plots(plots, [plots_sigffmap_list])

    return plots


def plots_sigffmb2(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    N = cvars.get("mbpfilter")['N']
    Wn_ary = cvars.get("mbpfilter")['Wn']

    if not cvars.get("plots_sigffmb2_hide"):
        for j in range(len(Wn_ary)):
            plots = add_plots(plots, get_sigffmb2(ohlc, N=N, Wn=Wn_ary[j], band=j, ax=ax))
            label = f"rFFmap {N},{Wn_ary[j]})"
            patches.append(mpatches.Patch(color=cvars.get('sigffmbstyle')['color'][j], label=label))
    else:  # + * JUST GET THE DATA, DONT PLOT
        for j in range(len(Wn_ary)):
            get_sigffmb2(ohlc, N=N, Wn=Wn_ary[j], band=j, ax=ax)

    # + * we now have all teh bands in cols 'sigffmb<band number>'
    # + ohlc['ffmap'] = (ohlc['sigffmb2']**2) * cvars.get('mbpfilter')['mx'][2]

    for j in range(len(Wn_ary)):
        ohlc[f'sigffmb2{j}'] = normalize_col(ohlc[f'sigffmb2{j}'])

    ohlc['ffmap2'] = ohlc['sigffmb20']
    for j in range(len(Wn_ary[1:])):
        ohlc['ffmap2'] = ohlc['ffmap2'] + ohlc[f'sigffmb2{j}']
    ohlc['ffmap2'] = 1 / ohlc['ffmap2']

    # + ohlc['ffmap'] = (
    # + ((ohlc['sigffmb0'] * cvars.get('mbpfilter')['mx'][0])
    # + (ohlc['sigffmb1'] * cvars.get('mbpfilter')['mx'][1])
    # + (ohlc['sigffmb2'] * cvars.get('mbpfilter')['mx'][2])
    # + )**2)

    # + print(ohlc.iloc[len(ohlc.index)-1]['ffmap'])
    # + ohlc['ffmap'] = ohlc['ffmap'].ewm(span=cvars.get("ffmap_span"))

    plots_sigffmap_list = mpf.make_addplot(
        ohlc['ffmap2'],
        ax=ax,
        type="line",
        color=cvars.get("ffmap2style")['color'],
        width=cvars.get("ffmap2style")['width'],
        alpha=cvars.get('ffmap2style')['alpha'],
    )

    patches.append(mpatches.Patch(color=cvars.get('ffmapstyle')['color'], label="Rohlc(sum(6f)^2)"))

    amin = float(ohlc['ffmap2'].min())
    amax = float(ohlc['ffmap2'].max())

    # + delta = (amax-amin)/100 # + * 1%
    delta = (amax - amin) * (cvars.get('lowpctline') / 100)

    ohlc['ffmapllim2'] = amin + delta
    ohlc['ffmapulim2'] = amax - delta

    ax.axhline(amin + delta,
        color=cvars.get("ffmap2lolimstyle")['color'],
        linewidth=cvars.get("ffmap2lolimstyle")['linewidth'],
        alpha=cvars.get('ffmap2lolimstyle')['alpha']
    )
    ax.axhline(amax - delta,
        color=cvars.get("ffmap2hilimstyle")['color'],
        linewidth=cvars.get("ffmap2hilimstyle")['linewidth'],
        alpha=cvars.get('ffmap2hilimstyle')['alpha']
    )

    plots = add_plots(plots, [plots_sigffmap_list])
    return plots


# + def ORG_plots_sigffmb(ohlc, **kwargs):
# + plots = kwargs['plots']
# + ax = kwargs['ax']
# + patches = kwargs['patches']
# + 
# + N=cvars.get("mbpfilter")['N']
# + Wn_ary=cvars.get("mbpfilter")['Wn']
# + 
# + if not cvars.get("loc_plots_sigffmb_hide"):
# + for j in range(len(Wn_ary)):
# + plots = add_plots(plots, get_sigffmb(ohlc, N=N, Wn = Wn_ary[j], band=j,ax=ax))
# + label = f"FFmap {N},{Wn_ary[j]})"
# + patches.append(mpatches.Patch(color=cvars.get('sigffmbstyle')['color'][j], label=label))
# + else: # + * JUST GET THE DATA, DONT PLOT
# + for j in range(len(Wn_ary)):
# + print(N,Wn,band)
# + 
# + get_sigffmb(ohlc, N=N, Wn = Wn_ary[j], band=j,ax=ax)
# + 
# + # + * now have all teh bands in cols 'sigffmb<band number>'
# + 
# + # + ohlc['ffmap'] = (ohlc['sigffmb2']**2) * cvars.get('mbpfilter')['mx'][2]
# + ohlc['ffmap'] = (
# + ((ohlc['sigffmb0'] * cvars.get('mbpfilter')['mx'][0])
# + *(ohlc['sigffmb1'] * cvars.get('mbpfilter')['mx'][1])
# + *(ohlc['sigffmb2'] * cvars.get('mbpfilter')['mx'][2])
# + )**2)
# + 
# + # + print(ohlc.iloc[len(ohlc.index)-1]['ffmap'])
# + # + ohlc['ffmap'] = ohlc['ffmap'].ewm(span=cvars.get("ffmap_span"))
# + 
# + plots_sigffmap_list = mpf.make_addplot(
# + ohlc['ffmap'],
# + ax=ax,
# + type="line",
# + color=cvars.get("ffmapstyle")['color'],
# + width=cvars.get("ffmapstyle")['width'],
# + alpha=cvars.get('ffmapstyle')['alpha'],
# + )
# + amin = float(ohlc['ffmap'].min())
# + amax = float(ohlc['ffmap'].max())
# + 
# + delta = (amax-amin)/100 # + * 1%
# + 
# + ohlc['ffmapllim'] = amin + delta
# + ohlc['ffmapulim'] = amax - delta
# + 
# + ax.axhline(amin + delta, color='magenta')
# + ax.axhline(amax - delta, color='cyan')
# + 
# + 
# + plots = add_plots(plots, [plots_sigffmap_list])
# + return plots

def plots_hilo(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_hilo_list = [mpf.make_addplot(ohlc["High"], ax=ax), mpf.make_addplot(ohlc["Low"], ax=ax)]
    patches.append(mpatches.Patch(color=cvars.get('hilostyle')['color'], label="Hi/Lo"))
    plots = add_plots(plots, plots_hilo_list)
    return plots


def plots_rohlc(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    # + ! can;t to -1 as teh **2 makes it positive, identical to the ohlc
    # + ohlc["rohlc"] = ohlc["Close"] * -1

    # ohlc["rohlc"] = 10000 - ohlc["Close"]
    ohlc["rohlc"] = ohlc["Close"].max() - ohlc["Close"]

    plots_rohlc_list = [mpf.make_addplot(
        ohlc["rohlc"],
        ax=ax,
        color=cvars.get('rohlcstyle')['color'],
        width=cvars.get('rohlcstyle')['width'],
        alpha=cvars.get('rohlcstyle')['alpha'],
    )]
    patches.append(mpatches.Patch(
        color=cvars.get('rohlcstyle')['color'],
        label="Rohlc"
    )
    )
    plots = add_plots(plots, plots_rohlc_list)
    return plots


def plots_hilolim(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    ohlc['hilim'] = ohlc['Close'] * cvars.get('closeXn')
    ohlc['lolim'] = ohlc['Close'] * 1 / cvars.get('closeXn')

    plots_hilolim_list = [mpf.make_addplot(ohlc["hilim"], ax=ax), mpf.make_addplot(ohlc["lolim"], ax=ax)]
    patches.append(mpatches.Patch(color=cvars.get('hilostyle')['color'], label="Xn"))
    plots = add_plots(plots, plots_hilolim_list)
    return plots


def plots_mav(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']
    mav = kwargs["mav"]
    color = kwargs["color"]
    width = kwargs["width"]
    # + alpha = kwargs["alpha"]

    ohlc[f'MAV{mav}'] = ohlc["Close"].rolling(mav).mean().values
    plots_mav_list = [mpf.make_addplot(ohlc[f"MAV{mav}"], ax=ax, color=color, width=width)]

    patches.append(mpatches.Patch(color=color, label=f"MA-{mav}"))
    plots = add_plots(plots, plots_mav_list)
    return plots


def plots_bb(ohlc, **kwargs):
    plots = kwargs['plots']
    band = kwargs['band']
    ax = kwargs['ax']
    patches = kwargs['patches']

    bbl = add_bbl_plots(ohlc, ax=ax, band=band)
    plots = add_plots(plots, [bbl[0], bbl[1]])
    patches.append(mpatches.Patch(color=cvars.get(f'bb{band}style')['color'], label=f"BB# + {band}"))

    return plots


def plots_2_bb(ohlc, **kwargs):
    plots = kwargs['plots']
    band = kwargs['band']
    ax = kwargs['ax']
    patches = kwargs['patches']

    bbl = add_2_bbl_plots(ohlc, ax=ax, band=band)
    plots = add_plots(plots, [bbl[0], bbl[1]])
    patches.append(mpatches.Patch(color=cvars.get(f'bb2{band}style')['color'], label=f"BB# + {band}"))

    return plots


def plots_bbavg(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    ohlc = add_bolbands(ohlc, ax=ax)

    bbl = add_bbl_plots(ohlc, ax=ax, band=1)
    bbl = add_bbl_plots(ohlc, ax=ax, band=2)
    bbl = add_bbl_plots(ohlc, ax=ax, band=3)

    plots_bbavg_list = add_bb_avg_plots(ohlc, ax=ax)
    plots = add_plots(plots, plots_bbavg_list)
    patches.append(mpatches.Patch(color=cvars.get('bblAvgstyle')["color"], label="BB3 Low"))
    patches.append(mpatches.Patch(color=cvars.get('bbmAvgstyle')["color"], label="BB3 Mid"))
    patches.append(mpatches.Patch(color=cvars.get('bbuAvgstyle')["color"], label="BB3 Hi"))
    return plots


def plots_2_bbavg(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    ohlc = add_2_bolbands(ohlc, ax=ax)

    bbl = add_2_bbl_plots(ohlc, ax=ax, band=1)
    bbl = add_2_bbl_plots(ohlc, ax=ax, band=2)
    bbl = add_2_bbl_plots(ohlc, ax=ax, band=3)

    plots_bbavg_list = add_2_bb_avg_plots(ohlc, ax=ax)
    plots = add_plots(plots, plots_bbavg_list)
    patches.append(mpatches.Patch(color=cvars.get('bbl2Avgstyle')["color"], label="BB3 Low"))
    patches.append(mpatches.Patch(color=cvars.get('bbm2Avgstyle')["color"], label="BB3 Mid"))
    patches.append(mpatches.Patch(color=cvars.get('bbu2Avgstyle')["color"], label="BB3 Hi"))
    return plots


def plots_hilodelta(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']
    plots = add_plots(plots, get_hilodelta(ohlc, ax=ax))
    patches.append(mpatches.Patch(color=cvars.get('hilodeltastyle')['color'], label="Hi/Lo Delta"))
    return plots


def plots_opcldelta(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']
    plots = add_plots(plots, get_opcldelta(ohlc, ax=ax))
    patches.append(mpatches.Patch(color=cvars.get('opcldeltastyle')['color'], label="Open/Close Delta"))
    return plots


def plots_deltadelta(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']
    plots = add_plots(plots, get_deltadelta(ohlc, ax=ax))
    patches.append(mpatches.Patch(color=cvars.get('deltadeltastyle')['color'], label="Delta Delta"))
    ax.axhline(y=cvars.get("delta_highlimit_sell"), color='cyan')
    ax.axhline(y=0.0, color='black')
    ax.axhline(y=cvars.get("delta_lowlimit_buy"), color='magenta')
    return plots


# + -------------------------------------------------------------
# +  COLOR CODES
# + -------------------------------------------------------------

def cclr():
    print(Style.RESET_ALL, end="")
    print(Fore.RESET, end="")
    print(Back.RESET, end="")


def pcCLR():
    return Style.RESET_ALL + Fore.RESET + Back.RESET


def pcDATA():
    return Fore.YELLOW + Style.BRIGHT


def pcINFO():
    return Fore.GREEN + Style.BRIGHT


def pcTEXT():
    return Style.BRIGHT + Fore.WHITE


def pcTOREM():
    return Fore.YELLOW + Back.BLUE + Style.BRIGHT


def pcFROREM():
    return Back.YELLOW + Fore.BLUE + Style.BRIGHT


def pcERROR():
    return Fore.RED + Style.BRIGHT


# + -------------------------------------------------------------
# +  TRIGGERS
# + -------------------------------------------------------------

def trigger_bb3avg(df, **kwargs):
    ax = kwargs['ax']
    cols = df['ID'].max()

    def tots(dfline, **kwargs):
        rs = float("Nan")
        m = float("Nan")
        # + !if there is a BUY and not a SELL, add the subtot as a neg value
        if not math.isnan(dfline['buy']) and math.isnan(dfline['sell']):
            m = dfline['buy'] * -1
        # + ! if there is a SELL and not a BUY, add the subtot as a pos value
        if not math.isnan(dfline['sell']) and math.isnan(dfline['buy']):
            m = dfline['sell']
        rs = m * dfline['qty']
        return (rs)

    def fillin(dfline, df, **kwargs):

        last_pct = float("Nan")
        # + waitfor()
        rs = float("Nan")
        if math.isnan(dfline['pct']):  # + ! in pct is empty
            if math.isnan(last_pct):  # + ! look to g.previous
                rs = float("Nan")  # + ! is also empty, set to o
            else:  # + ! if g.previous exists
                rs = last_pct  # + ! set to that
        else:  # + ! if pct not empty
            rs = dfline['pct']  # + ! use that
            last_pct = rs
        return rs

    def tfunc(dfline, **kwargs):
        action = kwargs['action']
        df = kwargs['df']
        g.idx = dfline['ID']
        CLOSE = dfline['Close']
        OPEN = dfline['Open']

        # + -------------------------------------------------------------------
        # + BUY
        # + -------------------------------------------------------------------
        is_a_buy = True
        is_a_sell = True

        if action == "buy":
            BUY_PRICE = None
            if g.idx == cols:  # * idx is the current index of rfow, cols is max rows... so only when arrived at last row
                # * load the test class
                # ! can do this outside loop? JWFIX
                tc = Tests(cvars, dfline, df, idx=g.idx)

                # * run test, passing the BUY test algo, or run is alt-S, or another external trigger, has been activated
                is_a_buy = \
                    (tc.buytest(cvars.get('testpair')[0]) or g.external_buy_signal) \
                    and g.buys_permitted  # * we haven't reached the maxbuy limit yet

                # * BUY is approved, so check that we are not runnng hot
                # ! cooldown is calculated by adding the current g.gcounter counts and adding the g.cooldown
                # ! value to arrive a the NEXT g.gcounter value that will allow buys.
                # !g.cooldown holds the number of buys


                if is_a_buy and (g.gcounter >= g.cooldown):
                    # * first get latest conversion price
                    g.conversion = get_last_price(g.spot_src, quiet=True)

                    # * set cooldown by setting the next gcounter number that will freeup buys
                    g.cooldown = g.gcounter + cvars.get("cooldown")
                    # * we are in, so reset the buy signal for next run
                    g.external_buy_signal = False
                    # ! check there are funds?? JWFIX

                    BUY_PRICE = CLOSE

                    # * calc new subtot and avg
                    # ! need to add current price and qty before doing the calc
                    # * these list counts are how we track the total number of purchases since last sell
                    state_ap('open_buys', BUY_PRICE)  # * adds to list of purchase prices since last sell
                    state_ap('qty_holding', g.purch_qty)  # * adds to list of purchased quantities since last sell, respectfully

                    # * calc avg price using weighted averaging, price and cost are [list] sums
                    g.subtot_cost, g.subtot_qty, g.avg_price = wavg(state_r('qty_holding'), state_r('open_buys'))

                    state_wr("last_avg_price",g.avg_price)
                    ax.set_facecolor("#f7d5de")

                    # * update the buysell records
                    g.df_buysell['subtot'] = g.df_buysell.apply(lambda x: tots(x), axis=1)
                    g.df_buysell['pct'].fillna(method='ffill', inplace=True)
                    g.df_buysell['pnl'].fillna(method='ffill', inplace=True)
                    g.df_buysell['pct'] = g.df_buysell.apply(lambda x: fillin(x, g.df_buysell), axis=1)
                    g.df_buysell['buy'].iloc[0] = BUY_PRICE
                    g.df_buysell['qty'].iloc[0] = g.purch_qty
                    bv = df['bb3avg_buy'].iloc[-1]  # + * gets last buy
                    sv = df['bb3avg_sell'].iloc[-1]  # + * gets last sell
                    tv = df['Timestamp'].iloc[-1]  # + * gets last timestamp
                    g.df_buysell['Timestamp'].iloc[0] = tv  # + * add last timestamp tp buysell record

                    # * increment run counter and make sure the historical max is recorded
                    g.current_run_count = g.current_run_count + 1
                    state_wr("current_run_count", g.current_run_count)

                    # * track ongoing number of buys since last sell
                    g.curr_buys = g.curr_buys + 1

                    g.buys_permitted = False if g.curr_buys >= cvars.get('maxbuys') else True

                    state_wr("last_buy_date", f"{tv}")
                    state_wr("curr_qty", g.subtot_qty)

                    if g.is_first_buy:
                        state_wr("first_buy_price", BUY_PRICE)
                        g.is_first_buy = False
                    state_wr("last_buy_price", BUY_PRICE)

                    order = {}
                    order["pair"] = cvars.get("pair")
                    # = order["funds"] = False
                    order["side"] = "buy"
                    order["size"] = truncate(g.purch_qty, 5)
                    order["price"] = CLOSE
                    order["order_type"] = "market"
                    # = order["stop_price"] = CLOSE * 1/cvars.get('closeXn')
                    # = order["upper_stop_price"] = CLOSE * 1
                    order["uid"] = g.gcounter #get_seconds_now() #! we can use g.gcounter as there is only 1 DB trans per loop
                    order["state"] = "submitted"
                    order["order_time"] = f"{dfline['Date']}"
                    state_wr("order", order)
                    orders(order)

                    #  calc total cost this run
                    ql =  state_r('qty_holding')
                    cl =  state_r('open_buys')

                    sess_cost = 0

                    for i in range(len(ql)): 
                        sess_cost = sess_cost + (cl[i] * ql[i])

                    newavg = (sum(cl)/sum(ql))/100


                    a = f"{order['size']:6.4f}"
                    b = f"{BUY_PRICE:6.4f}"
                    c = f"{order['size'] * BUY_PRICE:6.4f}"
                    d = f"{sess_cost:6.4f}"
                    e = f"{g.avg_price:06.4f}/{newavg:06.4f}"
                    


                    print(Fore.RED + f"Hold {a} @ {b} == {c}   St {g.subtot_cost:06.4f}, Sq {g.subtot_qty:06.4f}, avg {g.avg_price:06.4f}"+Fore.RESET)


                    # * adjust the purchase quantity
                    # * reduce the decimals of the number
                    g.purch_qty = g.purch_qty * (1 + (g.purch_qty_adj_pct / 100))
                    g.purch_qty = int(g.purch_qty * 1000) / 1000  # ! Smallest unit allowed (on CB) is 0.00000001

                    # * there's something to sell now
                    state_wr("purch_qty", g.purch_qty)
                    state_wr("open_buyscansell", True)

                    announce(what="buy")
                else:
                    BUY_PRICE = float("Nan")
            else:
                BUY_PRICE = float("Nan")
            return BUY_PRICE

        # + -------------------------------------------------------------------
        # + SELL
        # + -------------------------------------------------------------------
        if action == "sell":
            sell = None
            if g.idx == cols and state_r("open_buyscansell"):

                # * dump if we are maxed-out of buys
                if g.curr_buys >= cvars.get("maxbuys"):
                    if CLOSE > g.avg_price and cvars.get("bail_option_1"):
                        g.external_sell_signal = True

                tc = Tests(cvars, dfline, df, idx=g.idx)
                is_a_sell = tc.selltest(cvars.get('testpair')[1]) or g.external_sell_signal
                if is_a_sell:
                    # * first get latest conversion price
                    g.conversion = get_last_price(g.spot_src)

                    g.cooldown = 0  # * reset cooldown
                    g.buys_permitted = True  # * Allows buys again
                    g.purch_qty = cvars.get("purch_qty")  # * reset purchase qty
                    # state_wr("purch_qty", g.purch_qty)
                    g.external_sell_signal = False  # * turn off external sell signal

                    # * update buy counts
                    g.tot_buys = g.tot_buys + g.curr_buys
                    g.curr_buys = 0
                    state_wr("tot_buys", g.tot_buys)

                    SELL_PRICE = CLOSE

                    ax.set_facecolor("#ffffff")  # * make background pink when in BUY mode
                    # * calc new data
                    g.subtot_value = g.subtot_qty * SELL_PRICE  # * g.subtot_qty was set in the BUY routine

                    try:
                        g.last_pct_gain = ((g.subtot_value-g.subtot_cost)/g.subtot_cost)*100
                    except Exception as ex:
                        g.pct_gain_list = 0

                    #  ! save new data
                    state_ap("pct_gain_list", g.last_pct_gain)
                    state_ap("pnl_record_list", g.subtot_value - g.subtot_cost)
                    g.pnl_running = sum(state_r('pnl_record_list'))
                    state_wr("pnl_running", g.pnl_running)
                    g.pct_running = sum(state_r('pct_gain_list'))
                    state_wr("pct_running", g.pct_running)

                    # * track the local and total run count
                    state_ap("run_counts", g.current_run_count)
                    # + prev_ct = state_r("last_run_count")                     # + * get last run subtotal
                    # + this_ct = state_r("current_run_count")                  # + * get new current subtotal count
                    # + state_wr("largest_run_count", max(prev_ct, this_ct))    # + * save the laresget of the two
                    # + state_wr("last_run_count", this_ct)                     # + * set last count to current count
                    # + state_wr("current_run_count", 0)                        # + * clear current count
                    g.current_run_count = 0  # + * clear current count

                    this_qty = state_r("max_qty")
                    state_wr("max_qty", max(this_qty, g.subtot_qty))
                    state_wr("curr_qty", 0)

                    g.df_buysell['subtot'].iloc[0] = (g.subtot_cost)
                    g.df_buysell['qty'].iloc[0] = g.subtot_qty
                    g.df_buysell['pnl'].iloc[0] = g.pnl_running
                    g.df_buysell['pct'].iloc[0] = g.pct_running
                    g.df_buysell['sell'].iloc[0] = CLOSE
                    tv = df['Timestamp'].iloc[-1]
                    g.df_buysell['Timestamp'].iloc[0] = tv
                    state_wr("to", f"{tv}")
                    state_ap("pct_record_list", g.pct_running)
                    state_wr("open_buyscansell", False)
                    g.tot_sells = g.tot_sells + 1
                    state_wr("tot_sells", g.tot_sells)
                    state_wr("last_sell_price", SELL_PRICE)

                    # + g.subtot_cost = sum(state_r('open_buys'))
                    # + g.subtot_qty = sum(state_r('qty_holding'))
                    g.subtot_cost, g.subtot_qty, g.avg_price = wavg(state_r('qty_holding'), state_r('open_buys'))

                    order = {}
                    order["order_type"] = "sellall"
                    # = order["funds"] = False
                    order["side"] = "sell"
                    order["size"] = truncate(g.subtot_qty, 5)
                    order["price"] = CLOSE
                    # = order["stop_price"] = CLOSE * 1 / cvars.get('closeXn')
                    # = order["upper_stop_price"] = CLOSE * 1
                    order["pair"] = cvars.get("pair")
                    order["state"] = "submitted"
                    order["order_time"] = f"{dfline['Date']}"
                    order["uid"] = g.gcounter #get_seconds_now() #! we can use g.gcounter as there is only 1 DB trans per loop
                    state_wr("order", order)

                    # ! sell all and clear the counters
                    state_wr('open_buys', [])
                    state_wr('qty_holding', [])

                    g.avg_price = float("Nan")

                    orders(order)
                    # waitfor(["submitting SELL"])


                    a = f"{order['size']:6.4f}"
                    b = f"{SELL_PRICE:6.4f}"
                    c = f"{order['size'] * SELL_PRICE:6.4f}"
                    


                    print(Fore.GREEN + f"Sold {a} @ {b} == {c}")


                    # * now print a running total
                    print(get_running_bal())

                    announce(what="sell")

                else:
                    SELL_PRICE = float("Nan")
            else:
                SELL_PRICE = float("Nan")
            return SELL_PRICE

        return float("Nan")

    if len(df) != len(g.df_buysell.index):
        waitfor([f"End of data (index mismatch.  expecting {len(df)}, got {len(g.df_buysell.index)})"])

    df['ID'] = range(len(df))
    g.df_buysell['ID'] = range(len(df))

    df["bb3avg_buy"] = float("Nan")
    df["bb3avg_sell"] = float("Nan")

    g.df_buysell = g.df_buysell.shift(periods=1)

    # ! add new data to first row
    df['bb3avg_sell'] = df.apply(lambda x: tfunc(x, action="sell", df=df, ax=ax), axis=1)
    df['bb3avg_buy'] = df.apply(lambda x: tfunc(x, action="buy", df=df, ax=ax), axis=1)

    if g.avg_price > 0:
        ax.axhline(g.avg_price, color="indigo", linewidth=1, alpha=1)

    tmp = g.df_buysell.iloc[::-1] # ! here we have to invert the array to get the correct order
    p1 = mpf.make_addplot(tmp.buy, ax=ax, scatter=True, color="red", markersize=100, alpha=1, marker=6)  # + ^
    p2 = mpf.make_addplot(tmp.sell, ax=ax, scatter=True, color="green", markersize=100, alpha=1, marker=7)  # + v

    return [[p1], [p2]]


cvars = Cvars(g.cfgfile)
