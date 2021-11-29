import os
import json
import random
import calendar
import uuid
import gc
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
# from lib_tests_class import Tests
import lib_tests_class
from datetime import datetime, timedelta
import csv
import lib_globals as g
from shutil import copyfile
import subprocess
from subprocess import Popen
from colorama import Fore, Back, Style  # ! https://pypi.org/project/colorama/
import traceback
from scipy import signal
import time
import importlib


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

def update_db(tord):
    argstr = ""
    # print(tord)
    # waitfor()
    for key in tord:
        vnp = f"{key} = {tosqlvar(tord[key])}"
        argstr = f"{argstr},{vnp}"

    if cvars.get("mysql"):
        # g.dbc, g.cursor = getdbconn()
        uid = tord['uid']
        cmd = f"insert into orders (uid, session) values ('{uid}','{g.session_name}')"
        sqlex(cmd)
        g.logit.debug(cmd)
        cmd = f"UPDATE orders SET {argstr[1:]} where uid='{uid}' and session = '{g.session_name}'".replace("'None'", "NULL")
        sqlex(cmd)

        cmd = f"UPDATE orders SET bsuid = '{g.bsuid}' where uid='{uid}' and session = '{g.session_name}'"
        sqlex(cmd)

        credits = tord['price'] * tord['size']
        if tord['side'] == "buy":
            credits = credits * -1
        cmd = f"UPDATE orders SET credits = {credits} where uid='{uid}' and session = '{g.session_name}'"
        sqlex(cmd)
        cmd = f"UPDATE orders SET netcredits = credits-fees where uid='{uid}' and session = '{g.session_name}'"
        sqlex(cmd)


        cmd = f"select sum(credits) from orders where bsuid = {g.bsuid} and session = '{g.session_name}'"
        sumcredits = sqlex(cmd)[0][0]

        cmd = f"select sum(fees) from orders where bsuid = {g.bsuid} and  session = '{g.session_name}'"
        sumcreditsnet = sumcredits - sqlex(cmd)[0][0]

        cmd = f"UPDATE orders SET runtot = {sumcredits}, runtotnet = {sumcreditsnet} where uid='{uid}' and session = '{g.session_name}'"
        sqlex(cmd)

        # cmd = f"UPDATE orders SET runtot = {sumcredits} where uid='{uid}' and session = '{g.session_name}'"
        # sqlex(cmd)


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

def is_epoch_boundry(modby):
    epoch_time = int(time.time())
    g.epoch_boundry_countdown  = epoch_time % modby
    return g.epoch_boundry_countdown % modby


def tosqlvar(v):
    if not v:
        v = None
    v = f"'{v}'"
    return v


def exec_io(argstr, timeout=10):
    command = argstr.split()
    cp = Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    rs = False
    try:
        output, errors = cp.communicate(timeout=timeout)
        rs = output.strip()
    except Exception as ex:
        cp.kill()
        print("Timed out...")

    if not rs:
        g.logit.info(f"SENT: [{argstr}]")
        g.logit.info(f"RECIEVED: {rs}")
        g.logit.info(f"!!EMPTY RESPONSE!! Exiting:/")
        return False

        # = rs = {
        # = "message": "missing response... continuing",
        # = "settled": True,
        # = "order": "missing",
        # = "resp": ["missing"]
        # = }

    return rs


def orders(order, **kwargs):
    # nsecs = get_seconds_now()
    tord, argstr = filter_order(order)  # * filters out the unnecessary fields dependinG on order type

    # * submit order to remote proc, wait for replays

    if cvars.get('offline'):
        tord['fees'] = 0
        # ! these vals are takes from the empircal number of the CB dev sandbox transactions
        if order['side'] == "buy":
            tord['fees'] = (order['size'] * order['price']) * g.buy_fee # * sumulate fee

        if order['side'] == "sell":
            tord['fees'] = (order['size'] * order['price']) * g.sell_fee # * sumulate fee
            
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
        if not ufn:
            return False

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

    # update_db(tord, nsecs)
    update_db(tord)
    return True

def get_running_bal(**kwargs):
    version = 2
    ret = "all"
    sname = g.session_name
    try:
        version = kwargs['version']
    except:
        pass
    try:
        ret = kwargs['ret']
    except:
        pass
    try:
        sname = kwargs['session_name']
    except:
        pass

    if version == 1:
        # g.dbc, g.cursor = getdbconn()
        cmd = f"select * from orders where session = '{sname}'"
        rs = sqlex(cmd, ret=ret)

        # print("-----------------------------------")
        # print("rs",rs)
        # print("-----------------------------------")

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
            # print("-----------------------------------")
            # print("r", r)
            # print("-----------------------------------")
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
                # print("-----------------------------------")
                # print("profit", profit)
                # print("-----------------------------------")
                # print(Fore.YELLOW+f"PROFIT:------------------ {sum(sells)} - {sum(buys)} = {profit}"+Fore.RESET)
                res = Fore.CYAN + f"[{i:04d}] {Fore.CYAN}{adate} {Fore.YELLOW}${profit:6.2f}" + Fore.RESET
            i += 1
        # print("-----------------------------------")
        # print("res", res)
        # print("-----------------------------------")

        return float(profit)

    # * get the last runtotnet (rename? as ths is GROSS , not NET? - JWFIX)
    if version == 2:
        # profit = sqlex(f"SELECT t.runtotnet as profit FROM (select * from orders where side='sell' and session = '{sname}') as t order by id desc limit 1", ret=ret)[0]
        profit = sqlex(f"SELECT sum(netcredits) as profit FROM orders where session='{sname}'", ret=ret)[0]
        return profit


    if version == 3:
        # * don;t need lastid, as we are in teh 'sold' space, whicn means teh last order was a sell
        # lastid = sqlex(f"select id from orders where session = '{sname}' order by id desc limit 1 ", ret=ret)[0]
        # profit = sqlex(f"select sum(credits)-sum(fees) from orders where session = '{sname}' and id <= {lastid}", ret=ret)[0]
        profit = sqlex(f"select sum(credits)-sum(fees) from orders where session = '{sname}'", ret=ret)[0]
        return profit

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
    state_wr('config_file', g.cfgfile)
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
    state_wr("last_buy_price", 1e+10)

    state_wr("largest_run_count", 0)
    state_wr("last_run_count", 0)
    state_wr("current_run_count", 0)
    state_wr("pnl_running", 0)
    state_wr("pct_running", 0)
    state_wr("order", {})
    state_wr("last_sell_price", 0)
    state_wr("last_avg_price", 0)

    state_wr("curr_qty", 0)
    state_wr("delta_days", 0)
    state_wr("purch_qty", False)
    state_wr("run_counts", [])

    state_wr('open_buys', [])
    state_wr('qty_holding', [])


    # state_wr("pct_gain_list", [])
    # state_wr("pct_record_list", [])
    # state_wr("pnl_record_list", [])
    # state_wr("running_tot", [])

    state_wr("last_avg_price",float("Nan"))

    state_wr("pnl_running", float("Nan"))
    state_wr("pct_running", float("Nan"))

def loadstate():
    print("RECOVERING...")

    g.session_name = state_r('session_name')
    print("g.session_name",g.session_name)

    g.startdate = state_r("last_seen_date")
    print("g.startdate",g.startdate)

    g.tot_buys = state_r("tot_buys")
    print("g.tot_buys",g.tot_buys)

    g.tot_sells = state_r("tot_sells")
    print("g.tot_sells", g.tot_sells)

    g.current_run_count = state_r("current_run_count")
    print("g.current_run_count", g.current_run_count)

    g.subtot_qty = state_r("curr_qty")
    print("g.subtot_qty", g.subtot_qty)

    g.purch_qty = state_r("purch_qty")
    print("g.purch_qty", g.purch_qty)

    g.avg_price = state_r("last_avg_price")
    print("g.avg_price", g.avg_price)

    g.pnl_running = state_r("pnl_running")
    print("g.pnl_running", g.pnl_running)

    g.pct_running = state_r("pct_running")
    print("g.pct_running", g.pct_running)

# + -------------------------------------------------------------
# +  UTILS
# + -------------------------------------------------------------

def get_a_word():
    with open("data/words.txt", "r") as w:
        words = w.readlines()
    i = random.randint(0, len(words) - 1)
    g.session_name = words[i]
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
    findat["Run Name"] = f"{g.cwd}/{g.session_name}".strip()
    findat["Dataset"] = g.datasetname
    findat["Algos"] = f"{g.buyfiltername} / {g.sellfiltername}".strip()
    findat["Pair"] = cvars.get('pair').strip()
    findat["Total buys"] = g.tot_buys
    findat["Total sells"] = g.tot_sells
    findat["cooldown"] = cvars.get('cooldown')
    findat["purch_qty_adj_pct"] = cvars.get('purch_qty_adj_pct')
    uid = f"{g.uid}" #instance_num}_{uuid.uuid4().hex}" #! JWFIX useless to have this here
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

    print("*******************************************************")

    csvname = "./" + cvars.get('csvname')
    if not os.path.isfile(csvname): createcsv(csvname, print_order)
    with open(csvname, 'a') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=print_order_keys)
        writer.writerow(print_order)

    copyfile(f"config_{g.instance_num}.hcl", f"./{tfn}")

    # os.system("ssconvert results.csv results.xls")
    g.logit.info(f"Results saved in {csvname}")

    #* now save the df_allrecords
    adf = pd.read_csv('_allrecords.csv')
    fn = f"_allrecords_{g.instance_num}.json"
    g.logit.debug(f"Save {fn}")
    cvars.save(adf, fn)


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


def state_wr(name, v):
    # * if supposed to be a number, but it Nan...
    try:
        if math.isnan(v):
            return  #* just leave if value is Nan
    except:
        pass

    if g.state:  # ! array in mem exists - currently not in use
        g.state[name] = v
    else:
        try:
            with open(g.statefile) as json_file:
                data = json.load(json_file)
        except Exception as ex:
            handleEx(ex, f"Check the file '{g.statefile}' (for ex. at 'https://jsonlint.com/)'")
            exit(1)
        data[name] = v
        try:
            with open(g.statefile, 'w') as outfile:
                json.dump(data, outfile, indent=4)
        except Exception as ex:
            handleEx(ex, f"Check the file '{g.statefile}' (for ex. at 'https://jsonlint.com/)'")
            exit(1)
        data[name] = v


def state_ap(listname, v):
    if math.isnan(v):
        return  #* just leave if value is Nan
    if g.state:  # ! array in mem exists - currently not in use
        g.state[listname].append(v)
    else:
        with open(g.statefile) as json_file:
            data = json.load(json_file)
        data[listname].append(v)
        with open(g.statefile, 'w') as outfile:
            json.dump(data, outfile, indent=4)


def state_r(name, **kwargs):
    if g.state:  # ! array in mem exists... currently not in use
        return g.state[name]
    else:
        try:
            with open(g.statefile) as json_file:
                data = json.load(json_file)

            if type(data[name]) == list:
                data[name] = [x for x in data[name] if np.isnan(x) == False]

            return data[name]
        except:
            print(f"Attempting to read '{name}' from '{g.statefile}")
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
    # ! sdata = json.dumps(data)
    # + with open('_tmp', 'r') as file:    # + * then read it in again!!??
    # + sdata = file.read()

    if stop_at:
        print("waiting...\n")
        # + x=input(sdata)
        x = input()
        if x == "x":
            exit()
        if x == "n":
            return False
        if x == "y":
            return True
    # else:
    #     print(sdata)


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
    pair = kwargs['pair']
    timeframe = kwargs['timeframe']
    livect = f"({g.gcounter}/{cvars.get('datalength')})"

    # ft = f"{g.current_close:6.2f} INS=?"
    ft = f"{g.current_close:6.2f} INS={g.instance_num}/{g.session_name} "

    # # + BACkTEST
    # if cvars.get("datatype") == "backtest":
    #     metadatafile = f"{cvars.get('datadir')}/{cvars.get('backtestmeta')}"
    #     metadata = cvars.cload(metadatafile)
    #     # + atype = metadata['type']
    #     atype = g.datasetname
    #     pair = metadata['pair']
    #     timeframe = metadata['t_frame']
    #     # + fromdate = metadata['fromdate']
    #     fromdate = state_r("from")
    #     # + todate = metadata['todate']
    #     todate = state_r("to")
    #
    #     deltadays = days_between(fromdate.replace("_", " "), todate)
    #     state_wr("delta_days", f"{deltadays}")
    #     ft = f"{g.current_close:6.2f} INS={g.instance_num}/{g.session_name} ({deltadays})[{atype}] {pair} {timeframe} {livect} FROM:{fromdate}  TO:{todate}"
    #
    # # + LIVE
    # if cvars.get("datatype") == "live":
    #     atype = "LIVE"
    #     count = "N/A"
    #     exchange = "Binance"
    #     fromdate = "Ticker"
    #     todate = "Live"
    #     deltadays = days_between(fromdate, todate)
    #
    #     ft = f"{g.current_close:6.2f} INS={g.instance_num}/{g.session_name} ({deltadays})[{atype}] {pair} {timeframe} FROM:{fromdate}  TO:{todate}"
    #
    # # + RANDOM
    # if cvars.get("datatype") == "random":
    #     atype = "Random"
    #     count = "N/A"
    #     exchange = "N/A"
    #     fromdate = "N/A"
    #     todate = "N/A"
    #     deltadays = days_between(fromdate, todate)
    #
    #     ft = f"{g.current_close:6.2f} INS={g.instance_num}/{g.session_name} {livect} pts:{count}"

    # + g.subtot_cost, g.subtot_qty, g.avg_price = itemgetter(0, 1, 2)(list_avg(state_r('open_buys'),state_r('qty_holding')))
    # + g.subtot_qty = trunc(g.subtot_qty)
    # + g.subtot_cost = trunc(g.subtot_cost)

    g.pnl_running = truncate(state_r('pnl_running'), 5)
    g.pct_running = truncate(state_r('pct_running'), 5)

    rpt = f" {g.subtot_qty:8.2f} @ ${g.subtot_cost:8.2f}  ${g.running_total:6.2f}"

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
    tot_cost = 0
    adj_tot_cost = 0
    tot_qty = 0
    for i in range(len(shares)):
        adj_price = prices[i] * (1+cvars.get('buy_fee'))
        price = prices[i]
        tot_cost = tot_cost + (price * shares[i])
        adj_tot_cost = adj_tot_cost + (adj_price * shares[i])
        tot_qty = tot_qty + shares[i]
    try:
        avg = tot_cost / tot_qty
        adj_avg = adj_tot_cost / tot_qty
    except:
        avg = tot_cost
        adj_avg = adj_tot_cost


    # print(f"Calced subtot_qty = {tot_qty}")
    # print(f"Calced subtot_cost = {tot_cost}")
    return tot_cost, tot_qty, avg, adj_tot_cost, adj_avg

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

def make_steppers(df):
    startat = 4
    amat = 0
    stepct = 0
    df['steps']=range(len(df))

    def tfuncd(dfline, **kwargs):
        df = kwargs['df']
        idx = dfline['ID']
        if idx > 4:
            cval = df[df['ID'] == idx]['Close'].values[0]
            pval = df[df['ID'] == idx-1]['Close'].values[0]
            if cval < pval:
                g.stepctd = g.stepctd  -1
            else:
                g.stepctd = 0
            return int(g.stepctd)

    def tfuncu(dfline, **kwargs):
        df = kwargs['df']
        idx = dfline['ID']

        if idx > 4:
            cval = df[df['ID'] == idx]['Close'].values[0]
            pval = df[df['ID'] == idx-1]['Close'].values[0]

            if cval > pval:
                g.stepctu = g.stepctu  +1
            else:
                g.stepctu = 0

            return int(g.stepctu)

    df['stepsdn'] = df.apply(lambda x: tfuncd(x, df=df), axis=1)
    df['stepsup'] = df.apply(lambda x: tfuncu(x, df=df), axis=1)




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

        # * add some precalced data
        df['EMAlong'] = ta.ema(df['Close'],cvars.get('EMAxlong'))

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
        df['EMAlong'] = ta.ema(df['Close'],cvars.get('EMAxlong'))
        df["Date"] = pd.to_datetime(df.Timestamp, unit='ms')
        df.index = pd.DatetimeIndex(df['Timestamp'])
        ohlc = df.loc[:, ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'orgClose']]
        ohlc['ID'] = range(len(df))
        ohlc["Date"] = pd.to_datetime(ohlc.Timestamp, unit='ms')
        # + ohlc.index = pd.DatetimeIndex(df['Timestamp'])
        ohlc.index = ohlc['Date']

    # + -------------------------------------------------------------
    # + BACKTEST DATA
    # + -------------------------------------------------------------
    if cvars.get("datatype") == "backtest":
        datafile = f"{cvars.get('datadir')}/{cvars.get('backtestfile')}"
        df = cvars.load(datafile, maxitems=cvars.get("datalength"))

        df.rename(columns={'Date': 'Timestamp'}, inplace=True)
        df['orgClose'] = df['Close']

        if g.startdate:
            # + * calculate new CURRENT time, not starting time of chart
            # old_start_time = df.iloc[0]['Timestamp']
            # new_start_time = df.iloc[0]['Timestamp'] + dt.timedelta(minutes=5 * g.datawindow)
            # print("old/new start time:", old_start_time, new_start_time)
            # date_mask = (df['Timestamp'] > new_start_time)


    #! if teh last row must be the start_date, and there are 108 rows, and each row reps 5min...
    #! that teh ephc for teh last row is start_date+(108*5)m, so to make teh last row match the
    #! start_date, start_date must be start_date-(108*5)m which 540m, 32400s


            secs = 54000  #(cvars.get('datawindow')*2)*5
            # secs = 32400 + (300*(12*6)) #(cvars.get('datawindow')*2)*5
            # secs = 54000
            #! 32400 = 108*5*60    DATAWIN
            #! 129600 = 300*12*6
            # print(g.gcounter)
            # epoch = datetime.strptime(g.startdate, '%Y-%m-%d %H:%M:%S')
            epoch = (datetime.strptime(g.startdate, '%Y-%m-%d %H:%M:%S') - datetime(1970, 1, 1)).total_seconds()
#             print(secs,epoch)
#             exit()
            adj_startdate = datetime.fromtimestamp(epoch-secs)
            # adj_startdate = datetime.fromtimestamp(epoch+secs)

            # print(f"startdate: {g.startdate} -> adj_dtartdate: {adj_startdate} -> ")

# 2020-01-02 1577923200 1577988300

            # * apply date filer
            # date_mask = (df['Timestamp'] > g.startdate)
            date_mask = (df['Timestamp'] > adj_startdate)
            df = df.loc[date_mask]

        df["Date"] = pd.to_datetime(df['Timestamp'], unit='ms')
        df.index = pd.DatetimeIndex(df['Timestamp'])

        _start = (g.datawindow) + g.gcounter
        _end = _start + (g.datawindow)
        # _start = (g.datawindow) + g.gcounter%3
        # _end = _start + (g.datawindow)

        ohlc = df.iloc[_start:_end]

        # + ! copying a df generated complained that I am trying to modiofy a copy, so this is to create
        # + ! a copy that has no record that it si a copy. tmp fix, find a better way
        fn = f"_tmp1_{g.instance_num}.json"
        cvars.save(ohlc, fn)
        del ohlc
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

def get_bbDelta(df, **kwargs):
    ax = kwargs['ax']
    df['bbDelta'] = df['bbuAvg'] - df['bblAvg']

    bbDelta_plot = [
        mpf.make_addplot(
            df['bbDelta'],
            ax=ax,
            scatter=False,
            color=cvars.get('bbDeltastyle')['color'],
            width=cvars.get('bbDeltastyle')['width'],
            alpha=cvars.get('bbDeltastyle')['alpha'],
        )
    ]
    ax.axhline(y=cvars.get('bbDelta_lim'), color="black")
    return bbDelta_plot


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


def get_sigffdelta(df, **kwargs):
    ax = kwargs['ax']

    # def tfunc(dfline, **kwargs):
    #     df = kwargs['df']
    #     # if df['sigffdelta'][-1] < df['sigffdelta'][-2] and df['sigffdelta'][-2] > df['sigffdelta'][-3]:
    #     g.sigffdeltahi =  df['sigffdelta'].tail(10).max()
    #     print(g.sigffdeltahi)
    #     return g.sigffdeltahi
    #     # else:
    #     #     return g.sigffdeltahi
        #
    df['sigffdelta'] = (df['sigff']- df['sigff'].shift(5))**2

    g.sigffdeltahi =  df['sigffdelta'].tail(7).max()

    # df['sigffdeltahi'] = df.apply(lambda x: tfunc(x,df=df), axis=1)

    # df['sigffdeltahi'].fillna(method='ffill', inplace=True)

    sigffdelta_plot = mpf.make_addplot(
        df['sigffdelta'],
        ax=ax,
        type="line",
        color=cvars.get('overunder2style')['color'],
        width=cvars.get('overunder2style')['width'],
        alpha=cvars.get('overunder2style')['alpha'],
    )
    ax.axhline(y=cvars.get('sigffdeltahi_lim'), color='cyan')
    # ax.axhline(y=cvars.get('overunder_buy'), color='magenta')
    # ax.axhline(y=0.0, color='black')

    return [sigffdelta_plot]


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

    # return [plot_pt1]


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
    df['sigff'] = normalize_col(df['sigff'], df['Close'].min(), df['Close'].max())

    plots_sigff_list = mpf.make_addplot(  # + * flatter
        df["sigff"],
        ax=ax,
        type="line",
        color=cvars.get("sigffstyle")['color'],
        width=cvars.get("sigffstyle")['width'],
        alpha=cvars.get('sigffstyle')['alpha'],
    )
    return [plots_sigff_list]


def get_siglf(df, **kwargs):
    ax = kwargs['ax']

    # ! https://dsp.stackexchange.com/questions/19084/applying-filter-in-scipy-signal-use-lfilter-or-filtfilt

    # * siglf: lfilter is causal forward-in-time filtering only, similar to a real-life electronic filter.
    # * It can't be zero-phase. It can be linear-phase (symmetrical FIR), but usually isn't. Usually it adds
    # * different amounts of delay at different frequencies.

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
    return [plots_siglf_list]

def get_sigffmb(df, **kwargs):
    ax = kwargs['ax']
    band = kwargs['band']
    N = kwargs['N']
    Wn = kwargs['Wn']

    # def tfunc(dfline, **kwargs):
    #     df = kwargs['df']
    #     band = kwargs['band']
    #
    #     d = dfline[f'sigffmb{band}']  # + * the sig value, can be very small
    #     df = dfline['Close'] - d
    #
    #     nclose = dfline['Close']  # + (df*cvars.get('mbpfilter')["mx"][band])
    #
    #     return nclose

    colname = f'sigffmb{band}'
    df[colname] = 0

    b, a = signal.butter(N, Wn, btype="bandpass", analog=False)     #* get filter params
    sig = df['Close']                                               #* select data to filter
    sigff = signal.lfilter(b, a, signal.filtfilt(b, a, sig))        #* get the filter
    g.bag[f'sigfft{band}'].append(sigff[len(sigff) - 1])            #* store results in temp location
    df[colname] = backfill(g.bag[f'sigfft{band}'])                  #* fill data to match df shape

    # + df[colname] = df['Close'] + df[colname]                     #* add sig data to close
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

    # def tfunc(dfline, **kwargs):
    #     df = kwargs['df']
    #     band = kwargs['band']
    #     d = dfline[f'sigffmb2{band}']
    #     df = dfline['rohlc'] - d
    #     nclose = dfline['rohlc']  # + (df*cvars.get('mbpfilter')["mx"][band])
    #     return nclose

    colname = f'sigffmb2{band}'
    df[colname] = 0

    b, a = signal.butter(N, Wn, btype="bandpass", analog=False)
    sig = df['rohlc']
    sigff = signal.lfilter(b, a, signal.filtfilt(b, a, sig))
    g.bag[f'sigfft2{band}'].append(sigff[len(sigff) - 1])  #! g.bag[f'sigfft2{band}'] MUST be defined in lib_globals (for now)
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

# + --------------------------------------------------------------
# + GEMERATOR UIILS
# + --------------------------------------------------------------

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

def sqlex(cmd, **kwargs):
    ret="all"
    try:
        ret=kwargs['ret']
    except:
        pass

    g.logit.debug(f"SQL Command:{cmd}")
    rs=False
    try:
        g.cursor.execute("SET AUTOCOMMIT = 1")
        g.cursor.execute(cmd)
        g.dbc.commit()
        if ret == "all":
            rs = g.cursor.fetchall()
        if ret == "one":
            rs = g.cursor.fetchone()
            
    except Exception as ex:
        handleEx(ex, cmd)
        exit(1)

    return(rs)

def calcfees(rs_ary):
    fees = 0
    print(rs_ary) #XXX
    waitfor()
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

def plots_sigffdelta(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_sigffdelta_list = add_plots(plots, get_sigffdelta(ohlc, ax=ax))

    patches.append(mpatches.Patch(color=cvars.get('overunderstyle')['color'], label="O/U"))
    return plots_sigffdelta_list



def plots_pt1(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plot_pt1 = mpf.make_addplot(
        ohlc['one_pt'],
        ax=ax,
        type="line",
        color=cvars.get("pt1style")['color'],
        width=cvars.get("pt1style")['width'],
        alpha=1  # + cvars.get('tholostyle_I')['color'],
    )
    plots_pt1_list = add_plots(plots, plot_pt1)

    ax.axhline(y=0.0, color='black')
    ax.axhline(y=cvars.get("pt1_highlimit_sell"), color='cyan')
    ax.axhline(y=cvars.get("pt1_lowlimit_buy"), color='magenta')

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
    mx = cvars.get("mbpfilter")['mx']

    if not cvars.get("plots_sigffmb_hide"):
        for j in range(len(Wn_ary)):
            plots = add_plots(plots, get_sigffmb(ohlc, N=N, Wn=Wn_ary[j], band=j, ax=ax))
            label = f"FFmap {N},{Wn_ary[j]})"
            patches.append(mpatches.Patch(color=cvars.get('sigffmbstyle')['color'][j], label=label))
    else:  # + * JUST GET THE DATA, DONT PLOT
        for j in range(len(Wn_ary)):
            get_sigffmb(ohlc, N=N, Wn=Wn_ary[j], band=j, ax=ax)

    # * we now have all the bands in cols 'sigffmb<band number>'

    # for j in range(len(Wn_ary)):  # ! JWFIX ? XXX
    #     ohlc[f'sigffmb{j}'] = normalize_col(ohlc[f'sigffmb{j}'])  # * set all bands to teh same data range

    ohlc['ffmap'] = range(len(ohlc)) #* make new column from old
    for j in range(len(Wn_ary)):    #* loop throubn 6 band
        ohlc['ffmap'] = ohlc['ffmap'] + (ohlc[f'sigffmb{j}']*mx[j])  # * add them all together

    # print(ohlc['ffmap'])
    # ohlc['ffmap'] = 1 / ohlc['ffmap']   #* take the inverse


    plots_sigffmap_list = mpf.make_addplot(
        ohlc['ffmap'],
        ax=ax,
        type="line",
        color=cvars.get("ffmapstyle")['color'],
        width=cvars.get("ffmapstyle")['width'],
        alpha=cvars.get('ffmapstyle')['alpha'],
    )

    patches.append(mpatches.Patch(color=cvars.get('ffmapstyle')['color'], label="OHLC(sum(6f)^2) BUY"))

    amin = float(ohlc['ffmap'].min())
    amax = float(ohlc['ffmap'].max())

    delta = (amax - amin) * (cvars.get('lowpctline') / 100)

    # ax.axhline(amin + delta,
    #     color=cvars.get("ffmaplolimstyle")['color'],
    #     linewidth=cvars.get("ffmaplolimstyle")['linewidth'],
    #     alpha=cvars.get('ffmaplolimstyle')['alpha']
    # )
    # ax.axhline(amax - delta,
    #     color=cvars.get("ffmaphilimstyle")['color'],
    #     linewidth=cvars.get("ffmaphilimstyle")['linewidth'],
    #     alpha=cvars.get('ffmaphilimstyle')['alpha']
    # )

    ohlc['ffmapllim'] = amin + delta
    ohlc['ffmapulim'] = amax - delta

    if not cvars.get('plots_sigffmb_hide'):
        return(add_plots(plots, [plots_sigffmap_list]))
    else:
        return plots

def plots_sigffmb2(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    N = cvars.get("mbpfilter")['N']
    Wn_ary = cvars.get("mbpfilter")['Wn']
    mx = cvars.get("mbpfilter")['mx']

    if not cvars.get("plots_sigffmb2_hide"):
        for j in range(len(Wn_ary)):
            plots = add_plots(plots, get_sigffmb2(ohlc, N=N, Wn=Wn_ary[j], band=j, ax=ax))
            label = f"rFFmap {N},{Wn_ary[j]})"
            patches.append(mpatches.Patch(color=cvars.get('sigffmbstyle')['color'][j], label=label))
    else:  # + * JUST GET THE DATA, DONT PLOT
        for j in range(len(Wn_ary)):
            get_sigffmb2(ohlc, N=N, Wn=Wn_ary[j], band=j, ax=ax)

    # * we now have all teh bands in cols 'sigffmb<band number>'

    # for j in range(len(Wn_ary)):
    #     ohlc[f'sigffmb2{j}'] = normalize_col(ohlc[f'sigffmb2{j}'])


    ohlc['ffmap2'] = range(len(ohlc))  # * make new column from old
    for j in range(len(Wn_ary)):    #* loop throubn 6 band
        ohlc['ffmap2'] = ohlc['ffmap2'] + (ohlc[f'sigffmb2{j}']*mx[j])  # * add them all together
    # ohlc['ffmap2'] = 1 / ohlc['ffmap2']   #* take the inverse


    # ohlc['ffmap2'] = ohlc['sigffmb20']
    # for j in range(len(Wn_ary[1:])):
    #     ohlc['ffmap2'] = ohlc['ffmap2'] + ohlc[f'sigffmb2{j}']
    # ohlc['ffmap2'] = 1 / ohlc['ffmap2']

    plots_sigffmap2_list = mpf.make_addplot(
        ohlc['ffmap2'],
        ax=ax,
        type="line",
        color=cvars.get("ffmap2style")['color'],
        width=cvars.get("ffmap2style")['width'],
        alpha=cvars.get('ffmap2style')['alpha'],
    )

    patches.append(mpatches.Patch(color=cvars.get('ffmap2style')['color'], label="Rohlc(sum(6f)^2) SELL"))

    amin = float(ohlc['ffmap2'].min())
    amax = float(ohlc['ffmap2'].max())

    # + delta = (amax-amin)/100 # + * 1%
    delta = (amax - amin) * (cvars.get('lowpctline') / 100)

    ohlc['ffmapllim2'] = amin + delta
    ohlc['ffmapulim2'] = amax - delta

    # ax.axhline(amin + delta,
    #     color=cvars.get("ffmap2lolimstyle")['color'],
    #     linewidth=cvars.get("ffmap2lolimstyle")['linewidth'],
    #     alpha=cvars.get('ffmap2lolimstyle')['alpha']
    # )
    # ax.axhline(amax - delta,
    #     color=cvars.get("ffmap2hilimstyle")['color'],
    #     linewidth=cvars.get("ffmap2hilimstyle")['linewidth'],
    #     alpha=cvars.get('ffmap2hilimstyle')['alpha']
    # )

    if not cvars.get('plots_sigffmb2_hide'):
        return(add_plots(plots, [plots_sigffmap2_list]))
    else:
        return plots

def plots_hilo(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_hilo_list = [mpf.make_addplot(ohlc["High"], ax=ax), mpf.make_addplot(ohlc["Low"], ax=ax)]
    patches.append(mpatches.Patch(color=cvars.get('hilostyle')['color'], label="Hi/Lo"))
    plots = add_plots(plots, plots_hilo_list)
    return plots

def plots_lookback(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_lookback_list = [
                        mpf.make_addplot(ohlc["lblow"],
                        ax=ax,
                        color=cvars.get('lblowstyle')['color'],
                        width=cvars.get('lblowstyle')['width'],
                        alpha=cvars.get('lblowstyle')['alpha'])
    ]
    patches.append(mpatches.Patch(color=cvars.get('lblowstyle')['color'], label="Lookback/3"))
    plots = add_plots(plots, plots_lookback_list)
    return plots

def plots_upperclose(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_upperclose_list = [
                        mpf.make_addplot(ohlc["upperClose"],
                        ax=ax,
                        color=cvars.get('upperclosestyle')['color'],
                        width=cvars.get('upperclosestyle')['width'],
                        alpha=cvars.get('upperclosestyle')['alpha'])
    ]
    patches.append(mpatches.Patch(color=cvars.get('upperclosestyle')['color'], label="Upper"))
    plots = add_plots(plots, plots_upperclose_list)
    return plots

def plots_lowerclose(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_lowerclose_list = [
                        mpf.make_addplot(ohlc["lowerClose"],
                        ax=ax,
                        color=cvars.get('lowerclosestyle')['color'],
                        width=cvars.get('lowerclosestyle')['width'],
                        alpha=cvars.get('lowerclosestyle')['alpha'])
    ]
    patches.append(mpatches.Patch(color=cvars.get('lowerclosestyle')['color'], label="Upper"))
    plots = add_plots(plots, plots_lowerclose_list)
    return plots

def plots_amp(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    plots_amp_list = [
                        mpf.make_addplot(ohlc["amp"],
                        ax=ax,
                        color=cvars.get('lowerclosestyle')['color'],
                        width=cvars.get('lowerclosestyle')['width'],
                        alpha=cvars.get('lowerclosestyle')['alpha'])
    ]
    patches.append(mpatches.Patch(color=cvars.get('lowerclosestyle')['color'], label="AMP"))
    plots = add_plots(plots, plots_amp_list)
    g.amp_lim = g.CLOSE * cvars.get('amp_lim')
    ax.axhline(y=g.amp_lim, color="black")

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

def plots_ffmaps(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']

    ohlc['ffmaps'] = ohlc['ffmap2'] - ohlc['ffmap']
    ohlc['ffmaps'] = ohlc['ffmaps'].ewm(span=3).mean()
    # ohlc['ffmaps'] = ohlc['ffmaps'].ewm(span=4).mean()
    # ohlc['ffmaps'] = ohlc['ffmaps'].ewm(span=8).mean()
    # ohlc['ffmaps'] = ohlc['ffmaps'].ewm(span=8).mean()
    # ohlc['ffmaps'] = ohlc['ffmaps'].ewm(span=8).mean()
    # ohlc['ffmaps'] = ohlc['ffmaps'].ewm(span=16).mean()


    plots_ffmaps_list = [mpf.make_addplot(ohlc["ffmaps"], ax=ax)]
    patches.append(mpatches.Patch(color=cvars.get('ffmapsstyle')['color'], label="FFMAPs"))
    plots = add_plots(plots, plots_ffmaps_list)
    ax.axhline(0,0,color="black")
    ax.axhline(g.ffmaps_hithresh,color="cyan")
    ax.axhline(g.ffmaps_lothresh,color="magenta")

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

def plots_bbDelta(ohlc, **kwargs):
    plots = kwargs['plots']
    ax = kwargs['ax']
    patches = kwargs['patches']
    plots = add_plots(plots, get_bbDelta(ohlc, ax=ax))
    patches.append(mpatches.Patch(color=cvars.get('opcldeltastyle')['color'], label="BB3 Delta"))
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
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓

def process_buy(is_a_buy, **kwargs):
    ax = kwargs['ax']
    BUY_PRICE = kwargs['CLOSE']
    df = kwargs['df']
    dfline = kwargs['dfline']

    def tots(dfline, **kwargs):
        rs = float("Nan")
        m = float("Nan")
        # * if there is a BUY and not a SELL, add the subtot as a neg value
        if not math.isnan(dfline['buy']) and math.isnan(dfline['sell']):
            m = dfline['buy'] * -1 
        # * if there is a SELL and not a BUY, add the subtot as a pos value
        if not math.isnan(dfline['sell']) and math.isnan(dfline['buy']):
            m = dfline['sell']

        rs = m * dfline['qty']
        return (rs)



    g.stoplimit_price  = BUY_PRICE * (1-cvars.get('sell_fee')) #/0.99
    # print(f"stoplimit_price set to {g.stoplimit_price}  ({BUY_PRICE} * {1-cvars.get('sell_fee')})")

    # * show on chart we have something to sell
    ax.set_facecolor("#f7d5de")

    # * first get latest conversion price
    g.conversion = get_last_price(g.spot_src, quiet=True)

    # * set cooldown by setting the next gcounter number that will freeup buys
    # ! cooldown is calculated by adding the current g.gcounter counts and adding the g.cooldown
    # ! value to arrive a the NEXT g.gcounter value that will allow buys.
    # !g.cooldown holds the number of buys


    g.cooldown = g.gcounter + (g.current_run_count*3) #cvars.get("cooldown") # ! JWFIX '3' in config file
    # print(f"cooldown: {g.cooldown} / {g.current_run_count*3} / {g.gcounter}")
    # * we are in, so reset the buy signal for next run
    g.external_buy_signal = False
    # ! check there are funds?? JWFIX

    # * calc new subtot and avg
    # ! need to add current price and qty before doing the calc
    # * these list counts are how we track the total number of purchases since last sell
    state_ap('open_buys', BUY_PRICE)  # * adds to list of purchase prices since last sell
    state_ap('qty_holding', g.purch_qty)  # * adds to list of purchased quantities since last sell, respectfully
    # * calc avg price using weighted averaging, price and cost are [list] sums


    g.subtot_cost, g.subtot_qty, g.avg_price, g.adj_subtot_cost, g.adj_avg_price = wavg(state_r('qty_holding'), state_r('open_buys'))


    state_wr("last_avg_price",g.avg_price)
    state_wr("last_adj_avg_price",g.avg_price)

    # * update the buysell records
    g.df_buysell['subtot'] = g.df_buysell.apply(lambda x: tots(x), axis=1)  # * calc which col we are looking at and apply accordingly
    # g.df_buysell['pct'].fillna(method='ffill', inplace=True)                # * create empty holder for pct and pnl
    # g.df_buysell['pnl'].fillna(method='ffill', inplace=True)                
    # g.df_buysell['pct'] = g.df_buysell.apply(lambda x: fillin(x, g.df_buysell), axis=1)

    # * 'convienience' vars, 
    bv = df['bb3avg_buy'].iloc[-1]          # * gets last buy
    sv = df['bb3avg_sell'].iloc[-1]         # * gets last sell
    tv = df['Timestamp'].iloc[-1]           # * gets last timestamp

    # * insert latest data into df, and outside the routibe we shift busell down by 1, making room for next insert as loc 0 
    g.df_buysell['buy'].iloc[0] = BUY_PRICE
    g.df_buysell['qty'].iloc[0] = g.purch_qty
    g.df_buysell['Timestamp'].iloc[0] = tv  # * add last timestamp tp buysell record

    # * increment run counter and make sure the historical max is recorded
    g.current_run_count = g.current_run_count + 1
    state_wr("current_run_count", g.current_run_count)

    # * track ongoing number of buys since last sell
    g.curr_buys = g.curr_buys + 1

    # * update buy count ans set permissions
    g.buys_permitted = False if g.curr_buys >= cvars.get('maxbuys') else True

    # * save useful data in state file
    state_wr("last_buy_date", f"{tv}")
    state_wr("curr_qty", g.subtot_qty)

    if g.is_first_buy:
        state_wr("first_buy_price", BUY_PRICE)
        g.is_first_buy = False
    state_wr("last_buy_price", BUY_PRICE)

    # * create a new order
    order = {}
    order["pair"] = cvars.get("pair")
    # = order["funds"] = False
    order["side"] = "buy"
    order["size"] = truncate(g.purch_qty, 5)
    order["price"] = BUY_PRICE
    order["order_type"] = "market"
    # = order["stop_price"] = CLOSE * 1/cvars.get('closeXn')
    # = order["upper_stop_price"] = CLOSE * 1
    order["uid"] = g.uid #g.gcounter #get_seconds_now() #! we can use g.gcounter as there is only 1 DB trans per loop
    order["state"] = "submitted"
    order["order_time"] = f"{dfline['Date']}"
    state_wr("order", order)

    rs = orders(order)
    # * order failed
    if not rs:
        return float("Nan")

    #  calc total cost this run
    qty_holding_list =  state_r('qty_holding')
    open_buys_list =  state_r('open_buys')

    # * calc current total cost of session
    sess_cost = 0
    for i in range(len(qty_holding_list)): 
        sess_cost = sess_cost + (open_buys_list[i] * qty_holding_list[i])

    # * make pretty strings
    s_size = f"{order['size']:6.3f}"
    s_price = f"{BUY_PRICE:6.2f}"
    s_cost = f"{order['size'] * BUY_PRICE:6.2f}"
    # d = f"{sess_cost:6.4f}"
    # e = f"{g.avg_price:06.4f}"

    total_amt = g.purch_qty * BUY_PRICE
    g.est_buy_fee = total_amt * cvars.get('buy_fee')
    g.est_sell_fee = g.subtot_cost * cvars.get('sell_fee')
    g.running_buy_fee = g.running_buy_fee +  g.est_buy_fee
    g.covercost = g.running_buy_fee  + g.est_sell_fee
    # print(f"NEW COVERCOST: {g.covercost}")
    g.coverprice = g.avg_price + g.covercost
    # print(f"{g.avg_price} + {g.covercost} = {g.coverprice}")
    # * print to console
    str=[]
    str.append(f"[{g.gcounter:05d}]")
    str.append(f"[{order['order_time']}]")
    str.append(Fore.RED + f"Hold [{g.buymode}] " + Fore.CYAN + f"{s_size} @ ${s_price} = ${s_cost}" + Fore.RESET)
    str.append(Fore.GREEN + f"AVG: " + Fore.CYAN +  Style.BRIGHT + f"${g.avg_price:6.2f}"+Style.RESET_ALL)
    str.append(Fore.GREEN + f"COV: " + Fore.CYAN +  Style.BRIGHT + f"${g.coverprice:6.2f}"+Style.RESET_ALL)
    str.append(Fore.RED + f"Fee: " + Fore.CYAN + f"${g.est_buy_fee:3.2f}" + Fore.RESET )
    iline=str[0]
    for s in str[1:]:
        iline = f"{iline} {s}"
    print(iline)

    if g.buymode != "D":
        # * adjust purch_qty according to rules, and make number compatible with CB api
        if g.needs_reload:
            g.purch_qty = state_r("purch_qty")
        else:
            g.purch_qty = g.purch_qty * (1 + (g.purch_qty_adj_pct / 100))
            g.purch_qty = int(g.purch_qty * 1000) / 1000  # ! Smallest unit allowed (on CB) is 0.00000001



    # * update state file
    state_wr("purch_qty", g.purch_qty)
    state_wr("open_buyscansell", True)

    #* set new low threshholc
    # g.ffmaps_lothresh = min(dfline['ffmaps'], g.ffmaps_lothresh)


    # * make a sound
    announce(what="buy")
    
    return BUY_PRICE

#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
#   - ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓

def process_sell(is_a_sell, **kwargs):
    ax = kwargs['ax']
    SELL_PRICE = kwargs['CLOSE']
    df = kwargs['df']
    dfline = kwargs['dfline']


    # * all cover costs incl sell fee were calculated in buy

    ax.set_facecolor("#ffffff")  # * make background white when nothing to sell

    # * first get latest conversion price
    g.conversion = get_last_price(g.spot_src)

    g.cooldown = 0                  # * reset cooldown
    g.buys_permitted = True         # * Allows buys again
    g.external_sell_signal = False  # * turn off external sell signal
    state_wr("last_buy_price", 1e+10)

    # * update buy counts
    g.tot_buys = g.tot_buys + g.curr_buys
    g.curr_buys = 0
    state_wr("tot_buys", g.tot_buys)

    # * reset ffmaps lo limit
    #* set new low threshholc
    g.ffmaps_lothresh = cvars.get('ffmaps_lothresh')


    # * calc new data.  g.subtot_qty is total holdings set in BUY routine
    g.subtot_value = g.subtot_qty * SELL_PRICE  

    # * calc pct gain/loss relative to invesment, NOT capital
    g.last_pct_gain = ((g.subtot_value-g.subtot_cost)/g.subtot_cost)*100

    # * save current run count, incremented in BUY, then reset
    state_ap("run_counts", g.current_run_count)
    g.current_run_count = 0  # + * clear current count

    # * recalc max_qty, comparing last to current, and saving max, then reset
    this_qty = state_r("max_qty")
    state_wr("max_qty", max(this_qty, g.subtot_qty))
    state_wr("curr_qty", 0)

    # * update buysell record
    tv = df['Timestamp'].iloc[-1]

    g.df_buysell['subtot'].iloc[0] = (g.subtot_cost)
    g.df_buysell['qty'].iloc[0] = g.subtot_qty
    g.df_buysell['pnl'].iloc[0] = g.pnl_running
    g.df_buysell['pct'].iloc[0] = g.pct_running
    g.df_buysell['sell'].iloc[0] = SELL_PRICE
    g.df_buysell['Timestamp'].iloc[0] = tv

    # * record last sell time as 'to' field
    state_wr("to", f"{tv}")

    # # * record pct gain/loss of this session
    # state_ap("pct_record_list", g.pct_running)

    # * turn off 'can sell' flag, as we have nothing more to see now
    state_wr("open_buyscansell", False)

    #* record total number of sell and latest sell price
    g.tot_sells = g.tot_sells + 1
    state_wr("tot_sells", g.tot_sells)
    state_wr("last_sell_price", SELL_PRICE)

    # * create new order
    order = {}
    order["order_type"] = "sellall"
    # = order["funds"] = False
    order["side"] = "sell"
    order["size"] = truncate(g.subtot_qty, 5)

    order["price"] = SELL_PRICE
    # = order["stop_price"] = CLOSE * 1 / cvars.get('closeXn')
    # = order["upper_stop_price"] = CLOSE * 1
    order["pair"] = cvars.get("pair")
    order["state"] = "submitted"
    order["order_time"] = f"{dfline['Date']}"
    order["uid"] = g.uid #g.gcounter #get_seconds_now() #! we can use g.gcounter as there is only 1 DB trans per loop
    state_wr("order", order)

    rs = orders(order)
    # * order failed
    if not rs:
        return float("Nan")
    # * sell all (the default sell strategy) and clear the counters
    state_wr('open_buys', [])
    state_wr('qty_holding', [])


    # * cals final cost and sale of session
    purchase_price = g.subtot_cost             
    sold_price = g.subtot_qty * SELL_PRICE     


    # * calc gross value
    rp1 = get_running_bal(version=1, ret='all')
    s_rp1 = f"{rp1:6.2f}"

    # * cals net vals (-fees)
    rp2 = get_running_bal(version=2, ret='one')
    s_rp2 = f"{rp2:6.2f}"

    # * calc running total (incl fees)
    g.running_total = get_running_bal(version=3, ret='one')
    s_running_total = f"{g.running_total:6.2f}"



    # * pct of return relatve to holding (NOT INCL FEES)
    # g.pct_return = ((sold_price - purchase_price)/purchase_price) # ! x 100 for actual pct value
    # * (INCL FEES)

    # - EXAMPLE... buy at 10, sell at 20, $1 fee
    # - (20-(10+1))/20
    # - (20-11)/20
    # - 9/20
    # - 0.45  = 45% = profit margin
    # - 20 * (1+.50) = 29 = new amt cap
    g.pct_return = ( sold_price - (purchase_price+ g.covercost))/sold_price # ! x 100 for actual pct value
    if math.isnan(g.pct_return):
        g.pct_return = 0

    # * pct relative to capital, whuch SHOULD be (current price * 'capital')  (NOT INCL FEES)
    # g.pct_cap_return = (sold_price - purchase_price)/(SELL_PRICE * cvars.get('capital'))
    g.pct_cap_return = g.pct_return/(g.capital/g.subtot_qty) # x cvars.get('capital'))

    # print(f"g.pct_return: {g.pct_return}")
    # print(f"g.pct_cap_return: {g.pct_cap_return}")

    s_size = f"{order['size']:6.2f}"
    s_price = f"{SELL_PRICE:6.2f}"
    s_tot = f"{g.subtot_qty * SELL_PRICE:6.2f}"

    # * update DB with pct
    cmd = f"UPDATE orders set pct = {g.pct_return}, cap_pct = {g.pct_cap_return} where uid = '{g.uid }' and session = '{g.session_name}'"

    # ! JWFIX RELOAD EERROR sending nans

    sqlex(cmd)

    # * print to console
    g.est_buy_fee =  g.subtot_cost * cvars.get('buy_fee')
    g.est_sell_fee = g.subtot_cost * cvars.get('sell_fee')
    sess_gross = (SELL_PRICE -g.avg_price) * g.subtot_qty
    sess_net =  sess_gross - (g.running_buy_fee+g.est_sell_fee)
    total_fee = g.running_buy_fee+g.est_sell_fee
    g.covercost = total_fee * (1/g.subtot_qty)
    g.coverprice = g.covercost + g.avg_price

    # print("..........................................")
    # print(f"running total buy fee: {g.running_buy_fee}")
    # print(f"total sell fee: {g.est_sell_fee}")
    # print(f"total fee: {total_fee}")
    # print(f"purch qty: {g.subtot_qty}")
    # print(f"current average: {g.avg_price}")
    # print(f"virt covercost: {g.covercost}")
    # print(f"coverprice: {g.coverprice}")
    # print(f"close: {SELL_PRICE}")
    # print(f"avg price: {g.avg_price}")
    # print(f"gross profit: {sess_gross}")
    # print(f"net profit: {sess_gross - total_fee}")
    # print("------------------------------------------")
    # waitfor()
    str=[]
    str.append(f"[{g.gcounter:05d}]")
    str.append(f"[{order['order_time']}]")
    str.append(Fore.GREEN + f"Sold    "  + f"{s_size} @ ${s_price} = ${s_tot}")
    str.append(Fore.GREEN + f"AVG: " + Fore.CYAN +  Style.BRIGHT + f"${g.avg_price:6.2f}"+Style.RESET_ALL)
    str.append(Fore.GREEN + f"Fee: " + Fore.CYAN +  Style.BRIGHT + f"${g.est_sell_fee:3.2f}"+Style.RESET_ALL)
    str.append(Fore.GREEN + f"SessGross: " + Fore.CYAN +  Style.BRIGHT + f"${sess_gross:06.4f}"+Style.RESET_ALL)
    str.append(Fore.GREEN + f"SessFee: " + Fore.CYAN +  Style.BRIGHT + f"${g.covercost:3.2f}"+Style.RESET_ALL)
    str.append(Fore.GREEN + f"SessNet: " + Fore.CYAN +  Style.BRIGHT + f"${sess_net:6.2f}"+Style.RESET_ALL)
    str.append(Fore.RESET)
    iline=str[0]
    for s in str[1:]:
        iline = f"{iline} {s}"
    print(iline)

    # \f"[{g.gcounter:05d}] [{order['order_time']}] "+
    # =      Fore.GREEN + f"Sold {s_size} @ ${s_price} = ${s_tot}    PnL: ${(g.subtot_qty * SELL_PRICE) - g.subtot_cost:06.4f}  Fee: ${est_fee:3.2f}  TFee: ${total_fees_to_cover:3.2f}  AVG: ${g.avg_price:6.2f} "+Fore.RESET)

    if (g.subtot_qty * SELL_PRICE) < cvars.get("stop_at"):
        waitfor([f"Total < {cvars.get('stop_at')}"])

    # g.capital = g.capital + (g.capital * (g.pct_cap_return))
    # print(f"{g.capital}  * 1+{g.pct_cap_return}")

    g.capital = g.capital * (1+g.pct_cap_return)

    # state_ap("running_tot",rp1)

    # * this shows the number before fees

    str=[]
    str.append(f"{Back.YELLOW}{Fore.BLACK}")
    str.append(f"[{dfline['Date']}]")
    str.append(f"NEW CAP AMT: "+Fore.BLACK+Style.BRIGHT+f"{g.capital:6.5f}"+Style.NORMAL)
    str.append(f"Running Total:"+Fore.BLACK+Style.BRIGHT+f" ${s_running_total}"+Style.NORMAL)
    str.append(f"{Back.RESET}{Fore.RESET}")
    iline=str[0]
    for s in str[1:]:
        iline = f"{iline} {s}"
    print(iline)

    # * update available capital according to last gains/loss
    g.purch_qty = g.capital * g.purch_pct
    # * reset average price
    g.avg_price = float("Nan")

    announce(what="sell") # * make a noise

    g.bsuid = g.bsuid + 1

    return SELL_PRICE

    
# + -------------------------------------------------------------
# +  TRIGGERS
# + -------------------------------------------------------------

def trigger_bb3avg(df, **kwargs):
    ax = kwargs['ax']
    cols = df['ID'].max()
    g.current_close = df.iloc[len(df.index)-1]['Close']

    def tfunc(dfline, **kwargs):
        action = kwargs['action']
        df = kwargs['df']
        g.idx = dfline['ID']
        CLOSE = dfline['Close']
        OPEN = dfline['Open']
        STEPSDN = dfline['stepsdn']
        STEPSUP = dfline['stepsup']


        # + -------------------------------------------------------------------
        # + BUY
        # + -------------------------------------------------------------------
        is_a_buy = True
        is_a_sell = True

        if action == "buy":
            # BUY_PRICE = None
            if g.idx == cols:  # * idx is the current index of rfow, cols is max rows... so only when arrived at last row
                # * load the test class
                # ! can do this outside loop? JWFIX
                # importlib.reload(lib_tests_class)
                # # from lib_tests_class import Tests
                importlib.reload(lib_tests_class)
                tc = lib_tests_class.Tests(cvars, dfline, df, idx=g.idx)

                # * run test, passing the BUY test algo, or run is alt-S, or another external trigger, has been activated
                is_a_buy = is_a_buy and tc.buytest(cvars.get('testpair')[0]) or g.external_buy_signal
                is_a_buy = is_a_buy and g.buys_permitted       # * we haven't reached the maxbuy limit yet
                # is_a_buy = is_a_buy and STEPSDN <= -2              # * at least 3 previous downs

                # * BUY is approved, so check that we are not runnng hot
                g.uid = uuid.uuid4().hex
                # if is_a_buy and (g.gcounter >= g.cooldown or CLOSE < dfline['lblow']):
                # if is_a_buy and (g.gcounter >= g.cooldown):


                # if cvars.get('xflag01'):
                #     is_a_buy = is_a_buy and (g.gcounter >= g.cooldown or CLOSE < dfline['lblow'])
                # else:
                #     is_a_buy = is_a_buy and (g.gcounter >= g.cooldown)

                if cvars.get('xflag01'):
                    is_a_buy = is_a_buy and (CLOSE < dfline['lblow'])

                # * make sure we have enough to cover
                checksize = CLOSE * g.purch_qty
                reserve = cvars.get('reserve_cap')
                allocated = (reserve * CLOSE)
                # allocated = (g.capital * CLOSE

                is_a_buy = is_a_buy and checksize < allocated
                if is_a_buy:
                    BUY_PRICE = process_buy(is_a_buy, ax=ax, CLOSE=CLOSE, df=df, dfline=dfline)
                else:
                    BUY_PRICE = float("Nan")

            else:
                BUY_PRICE = float("Nan")
            return BUY_PRICE

        # + -------------------------------------------------------------------
        # + SELL
        # + -------------------------------------------------------------------
        if action == "sell":
            if g.idx == cols and state_r("open_buyscansell"):
                # * first we check is we need to apply stop-limit rules
                limitsell = False
                # print(f":: {CLOSE} - {g.stoplimit_price}")
                if CLOSE <= g.stoplimit_price and cvars.get('maxbuys') == 1:
                    print(f"STOP LIMIT OF {g.stoplimit_price}!")
                    limitsell = True
                    g.external_sell_signal = True

                importlib.reload(lib_tests_class)
                tc = lib_tests_class.Tests(cvars, dfline, df, idx=g.idx)

                is_a_sell = is_a_sell and tc.selltest(cvars.get('testpair')[1]) or g.external_sell_signal

                if is_a_sell:
                    g.uid = uuid.uuid4().hex
                    if limitsell:
                        SELL_PRICE = process_sell(is_a_sell, ax=ax, CLOSE=g.stoplimit_price, df=df, dfline=dfline)
                        g.stoplimit_price = 1e-10
                    else:
                        SELL_PRICE = process_sell(is_a_sell, ax=ax, CLOSE=CLOSE, df=df, dfline=dfline)
                    os.system("touch /tmp/_sell")
                    g.covercost = 0
                    g.running_buy_fee = 0


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
        ax.axhline(g.avg_price+g.covercost, color="indigo", linewidth=1, alpha=0.5)


    tmp = g.df_buysell.iloc[::-1] # ! here we have to invert the array to get the correct order
    colors = ['blue' if v == 1 else 'red' for v in tmp["mclr"]]
    p1 = mpf.make_addplot(tmp['buy'], ax=ax, scatter=True, color=colors, markersize=200, alpha=0.4,  marker=6)  # + ^
    p2 = mpf.make_addplot(tmp['sell'], ax=ax, scatter=True, color="green", markersize=200, alpha=0.4, marker=7)  # + v

    #* add to MACD




    #* get rid of everything we are not seeing
    g.df_buysell = g.df_buysell.head(len(df))

    return [[p1], [p2]]

# print("================= ",g.cfgfile)
cvars = Cvars(g.cfgfile)
g.session_name = get_a_word()

