#!/usr/bin/python3.9
import lib_ohlc as o
import lib_globals as g
from colorama import Fore, Back, Style
from colorama import init
init()

# g.dbc, g.cursor = o.getdbconn(host="108.161.133.254")
g.dbc, g.cursor = o.getdbconn()

cmd = f"select * from orders"
rs = o.sqlex(cmd)
g.cursor.close()  # ! JWFIX - open and close here?

def get_running_bal(rs):
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
            # print(Fore.RED + f"Bought: {(aqty*aclose):=6.4f}"+Fore.RESET)
            buys.append(v)
        if aside == "sell":
            # print(Fore.GREEN + f"  Sold: {(aqty*aclose):6.4f}"+Fore.RESET)
            sells.append(v)
            profit = sum(sells) - sum(buys)
            # tot_profit = tot_profit + profit
            # print(Fore.YELLOW+f"PROFIT:------------------ {sum(sells)} - {sum(buys)} = {profit}"+Fore.RESET)
            res = Fore.CYAN + f"[{i:04d}] {Fore.CYAN}{adate} {Fore.MAGENTA}{profit:6.0f}" + Fore.RESET
        i += 1
    return res

print(get_running_bal(rs))
