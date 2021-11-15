#!/usr/bin/python3.9
import lib_ohlc as o
import lib_globals as g
import logging
import getopt
import sys
from colorama import Fore, Back, Style
from colorama import init
init()

# + ≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡
argv = sys.argv[1:]
try:
    opts, args = getopt.getopt(argv, "-hs:", ["help", "session="])
except getopt.GetoptError as err:
    sys.exit(2)

session_name = ""

for opt, arg in opts:
    if opt in ("-h", "--help"):
        print("-s, --session   session name")
        sys.exit(0)

    if opt in ("-s", "--session"):
        session_name = arg
# + ≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡

g.logit = logging
g.logit.basicConfig(
    filename="/home/jw/src/jmcap/ohlc/logs/ohlc.log",
    filemode='a',
    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
    level=o.cvars.get('logging')
)
stdout_handler = g.logit.StreamHandler(sys.stdout)

# g.dbc, g.cursor = o.getdbconn(host="108.161.133.254")
g.dbc, g.cursor = o.getdbconn()
cmd = f"SELECT  * FROM orders WHERE session = '{session_name}'"

print(cmd)
rs = o.sqlex(cmd)
g.cursor.close()  # ! JWFIX - open and close here?

sess_cost = 0

def get_running_bal(rs):
    global sess_cost
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
    c_pct = 15



    buys = []
    sells = []
    fees = []
    tot_profit = 0
    i = 1
    res = False
    for r in rs:
        aclose = r[c_price]
        aside = r[c_side]
        fee = r[c_fees]
        aqty = r[c_size]
        adate = r[c_order_time]
        pct = r[c_pct]
        tcost =aqty*aclose
    
        s_aqty = f"{aqty:6.4f}"
        s_close = f"{aclose:6.4f}"
        s_tcost = f"{tcost:6.4f}"

        if aside == "buy":
            sess_cost = sess_cost + tcost

            print(Fore.RED + f"Hold {s_aqty} @ ${s_close} == ${s_tcost} "+Fore.RESET)

            buys.append(tcost)
            fees.append(fee)


        if aside == "sell":
            sess_pct = ((tcost - sess_cost)/tcost) * 100
            s_pct = f"{pct:5.2f}"

            print(Fore.GREEN + f"Sold {s_aqty} @ ${s_close} == ${s_tcost} ({s_pct}%)")

            sells.append(tcost)
            fees.append(fee)


            tfees = sum(fees)
            profit = (sum(sells) - sum(buys))-tfees

            
            # tot_profit = tot_profit + profit
            # print(Fore.YELLOW+f"PROFIT:------------------  {profit}"+Fore.RESET)
            res = Fore.YELLOW + f"[{i:04d}] {adate}  ${profit:6.3f}  (fees: ${tfees:6.3})" + Fore.RESET
            print(res)
            sess_cost = 0
        i += 1
    return res

print(get_running_bal(rs))
