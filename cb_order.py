# + !/usr/sbin/python
from __future__ import print_function
import sys
import auth_client as cbp
import public_client as pub
import json
import simplejson
from decimal import Decimal
import decimal
import itertools
import base64
import uuid
import sys,getopt
import time
import math
import coinbase
import lib_ohlc as o
import pickle
import pprint as pp
# + import logging
import lib_globals as g
import json
from decimal import Decimal
from colorama import init
from colorama import Fore, Back, Style
from lib_cvars import Cvars
# + !  ?// 🟠 🔥 🏹 🎯 ❗ 📝 📈 👇 👆📉 ▼ ▲ ⭐  ✅ ═

o.cvars = Cvars(g.cfgfile)

BASE = False
QUOTE = False

extra = {'mod_name': 'cb_order'}
# + + ┌───────────────────────────────────────────────────
# + + │ 🟠 functions
# + + └───────────────────────────────────────────────────

def help():
    opttxt = """
    No options entered

    BUY 
    ./cb_test.py -m buy -z 0.1 -P BTC-USD -p 42000 -U 42100 -t limit -S 0%

    -P  --pair        BTC-USD
    -p  --price       1000.00
    -f  --funds       ???
    -t  --type        market|limit
    -z  --size        1111.0
    -m  --side        buy|sell
    -S  --stop_price  1110.0 | 1%
    -U  --upper_stop_price  1110.0 | 1%

    """
    return opttxt



# + def results(title,data, output=False):
# + if (isinstance(data, dict)):    # + * if ;data' is a dictionary...
# + _data = dict(data)          # + * make a copy ?
# + for key in _data:           # + * loop thru keys and print
# + if (output):
# + o.eprint(f"{key}:\t {_data[key]}")
# + return(_data)
# + 
# + if (isinstance(data, list)):
# + if  (len(data) == 0):
# + if (output):
# + o.eprint("Nothing to do (there are no open orders)")
# + for item in data:
# + if (isinstance(item,list)):
# + if (output):
# + o.eprint(f"{item}")
# + if (isinstance(item, dict)):
# + for key in item:
# + if (output):
# + o.eprint(f"{key}:\t {item[key]}")
# + if (output):
# + o.eprint("")
# + return(data)
def get_creds(**kwargs):
    keys = o.get_secret(provider=kwargs['provider'], apitype=kwargs['apitype'])
    key = keys['key']
    b64secret = keys['secret']
    passphrase = keys['passphrase']
    api_url = "https://"+o.cvars.get("creds")["api_url"]
    ac = cbp.AuthenticatedClient(api_url=api_url, key=key, secret=b64secret, passphrase=passphrase)
    pc = pub.PublicClient(api_url=api_url)
    return ac, pc

def get_exchangerate(pair):
    ticker = pc.get_product_ticker(product_id=pair)
    # + pp.pprint(ticker)
    return(float(ticker['price']))

def get_account_for(asset, aclist):
    global rs_ary
    acct = False
    if (isinstance(aclist, list)):
        if  (len(aclist) == 0):
            o.eprint("Nothing to do")
        for item in aclist:
            if (isinstance(item,list)):
                o.eprint(f"{item}")
            if (isinstance(item, dict)):
                for key in item:
                    if ((key == 'currency') and (item[key] == asset)):
                        acct = item.copy()
    return(acct)

def getarg(dopts, lk, sk, default, **kwargs):
    try:
        ontrue = kwargs['ontrue']
    except:
        ontrue = False

    r=default
    try:
        try:
            r = dopts[lk] # + * try long key
        except:
            r = dopts[sk] # + try short key
    except:
        r = default

    if r and ontrue:
        r = ontrue

    return(r)

def typefix(v):
    """
    If the impout is a number string, returns as a float
    """
    try:
        v = float(v)
    except:
        pass
    return(v)

def getBalance(pair):
    acctData = get_account_for(BASE, ac.get_accounts())
    base_bal=acctData['balance']
    # + pp.pprint(acctData)
    acctData = get_account_for(QUOTE, ac.get_accounts())
    quote_bal=acctData['balance']
    # + pp.pprint(acctData)
    # + exit()
    # + max = acctData['balance']
    return(float(base_bal),float(quote_bal))

def picksave(data, target):
    with open(target, 'wb') as handle:
        pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)  # + * save pickle file

def checkargs(a):
    if not a['_pair']:
        o.eprint("Missing -pair (-P)")
        exit(1)

    # + if not _funds:
    # + o.eprint("Missing -funds (-f)")
    # + exit()

    if a['_cancelall'] or a['_sellall']:
        pass
    else:
        if not a['_size']:
            o.eprint("Missing -size (-z)")
            exit(1)
        if not a['_side']:
            o.eprint("Missing -side (-m)")
            exit(1)
        if not a['_order_type']:
            o.eprint("Missing -type (-t)  'market' | 'limit' ")
            exit(1)
        if a['_order_type'] == "limit":
            if not a['_stop_price']:
                o.eprint("Missing --stop_price (-S)")
                exit(1)

def get_order_id(rs):
    try:
        return rs['id']
    except:
        return False

def getargsary(dopts):
    a={}
    # + * use a dict from the tuples ... lopping thru touple caused reassignment of vars :/ ?    a = {}
    a['_pair'] = getarg(dopts,'--pair', "-P", False)
    a['_funds'] = getarg(dopts,"--funds","-f",False)
    a['_price'] = getarg(dopts,"--price","-p",False)
    a['_side'] = getarg(dopts,"--side","-m",False)
    a['_order_type'] = getarg(dopts,"--type","-t",False)
    a['_size'] = getarg(dopts,"--size","-z",False)
    a['_upper_stop_price'] = getarg(dopts,"--upper_stop_price","-U",False)
    a['_stop_price'] = getarg(dopts,"--stop_price","-S",False)
    a['_uid'] = getarg(dopts,"--uid","-u",False)
    a['_cancelall'] = True if a['_order_type'] == 'cancelall' else False
    a['_sellall'] = True if a['_order_type'] == 'sellall' else False

    return a

init()
rs_ary = {}
rs = False
order_id = False
# + 
# + logging.basicConfig(input_filename="logs/cb_order.log",
# + filemode='a',
# + format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
# + datefmt='%H:%M:%S',
# + level=logging.DEBUG)


ac = False
pc = False

if o.cvars.get('creds')["name"] == "coinbase_sandbox":
    ac, pc = get_creds(provider='coinbase', apitype='sandbox')
if o.cvars.get('creds')["name"] == "coinbase_jmcap":
    ac, pc = get_creds(provider='coinbase', apitype='jmcap')


# + + ┌───────────────────────────────────────────────────
# + + │ 🟠 command line args parsing
# + + └───────────────────────────────────────────────────

argv = sys.argv[1:]

try:
    if len(argv) ==0:
        o.eprint(help())
        sys.exit(2)
    opts, args = getopt.getopt(argv, "P:p:f:t:z:m:S:U:u:", ["pair=", "price=","funds=", "type=","size=", "side=", "stop_price=", "upper_stop_price=", "uid="])
except Exception as ex:
    o.handleEx(ex,argv)
    exit(1)

a = getargsary(dict(opts))
checkargs(a)

BASE = a['_pair'].split("-")[0]
QUOTE = a['_pair'].split("-")[1]

# + for key in a: o.eprint(key,a[key])

# + + ≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡
# + + ┌───────────────────────────────────────────────────
# + + │ 🟠 Cancal All Orders
# + + └───────────────────────────────────────────────────
if a['_cancelall']:
    rs = ac.cancel_all()
    # + ! 'cancel_all()' does nto return any data, so we need to made some up so it can get process liek tehotehr orders
    rs = {}
    rs['id'] = 'noid'
    rs['settled'] = True
    order_id = get_order_id(rs)
    g.logging.info("-------- cancellall")
    g.logging.debug([rs])
    # + logging.debug(rs)
    rs_ary["message"] = 'All orders cancelled'



# + + ┌───────────────────────────────────────────────────
# + + │ 🟠 Sell All Holdings
# + + └───────────────────────────────────────────────────
if a['_sellall']:
    baseTot,quoteTot = getBalance(a['_pair'])

    rs = ac.place_order(
        product_id=a['_pair'],
        side='sell',
        order_type='market',
        size=baseTot,
    )
    order_id = get_order_id(rs)
    g.logging.info("-------- sellall")
    g.logging.debug([rs])


    # + rs_ary['settled'] = 'False'

# + + ┌───────────────────────────────────────────────────
# + + │ 🟠 Market Buy
# + + └───────────────────────────────────────────────────
if a['_order_type'] == "market":
    base_bal,quote_bal = getBalance(a['_pair'])
    exr = get_exchangerate(a['_pair'])

    # + * buying ETH (base), so need BTC (quote), 1 eth - 0.7 btc
    # + print(f"Have {base_bal} of {BASE}")
    # + print(f"Have {quote_bal} of {QUOTE}")
    # + print(f"Need {float(a['_size']) * exr} of {QUOTE} to buy {float(a['_size'])} of {BASE}")
    # + print(f"Is {quote_bal} > {float(a['_size']) * exr}")

    if quote_bal > float(a['_size']) * exr:
        o.eprint(f"ac.place_market_order(product_id={a['_pair']},side={a['_side']}, size={a['_size']})")
        # + o.waitfor()
        rs = ac.place_market_order(product_id=a['_pair'],side=a['_side'], size=a['_size'])
        order_id = get_order_id(rs)
        g.logging.info("-------- market buy")
        g.logging.debug(rs)
        rs_ary["message"] = 'Market Buy order submitted'
    else:
        msg =  f"Insufficient funds ({quote_bal:10f} BTC is not enough to buy {a['_size']} ETH )"
        rs_ary["message"] = msg
        g.logging.info(msg)
        exit()

# + * ┌───────────────────────────────────────────────────
# + * │ 🟠 Manage I/O
# + * └───────────────────────────────────────────────────

# + ! The order respone loosk like print(this..)
# + - {   'created_at':       datetime.datetime(2021, 11, 1, 15, 15, 15, 973587),
# + -     'executed_value':   Decimal('0'),
# + -     'fill_fees':        Decimal('0'),
# + -     'filled_size':      Decimal('0'),
# + -     'id':               '39aad785-af8a-4d2f-ac82-b6202d5aa95b',
# + -     'post_only':        False,
# + -     'product_id':       'ETH-BTC',
# + -     'settled':          False,
# + -     'side':             'sell',
# + -     'size':             Decimal('3.18'),
# + -     'status':           'pending',
# + -     'stp':              'dc',
# + -     'type':             'market'
# + - }


# + ! JWFIX
# + ufn = a['_uid'] # + f"{uuid.uuid4().hex}"

ufn = rs['id'] # + f"{uuid.uuid4().hex}"
full_ufn = f"records/B_{ufn}.ord"
picksave(rs,full_ufn)

rs_ary["order"] = full_ufn                 # + * store order pickle file name in array
rs_ary["resp"] = []                        # + * make an list to hold the repsponces to that order
# + rs_ary["settled"] = False
rs_ary["message"] = "Processing..."

istrue = False if order_id else True
fc = 0
while (istrue == False):                        # + * loop until we get a success reply
    # + ! the status reports look like this

    # + - {
    # + -  'created_at':      datetime.datetime(2021, 11, 1, 15, 15, 15, 979464),
    # + -  'done_at':         '2021-11-01T15:15:15.979464Z',
    # + -  'done_reason':     'canceled',
    # + -  'executed_value':  Decimal('0E-16'),
    # + -  'fill_fees':       Decimal('0E-16'),
    # + -  'filled_size':     Decimal('0E-8'),
    # + -  'id':              '39aad785-af8a-4d2f-ac82-b6202d5aa95b',
    # + -  'post_only':       False,
    # + -  'product_id': '    ETH-BTC',
    # + -  'profile_id':      'dfcb5c86-f42e-4564-93ca-678fa831753b',
    # + -  'settled':         True,
    # + -  'side':            'sell',
    # + -  'size':            Decimal('0E-8'),
    # + -  'status':          'done',
    # + -  'type':            'market'
    # + - }

    # + o.eprint("checking...")
    time.sleep(1)
    # + rfn = rs['id']  # + f"{uuid.uuid4().hex}"
    rfn = f"{full_ufn}.r_{fc}"                    # + * incrementally name teh resp files
    rs_ary["resp"].append(rfn)                   # + * store in list

    try:                                        # + * for empty replies, like 'cancel_all()', we make out own data;
        order_stat = ac.get_order(rs['id'])
    except:
        order_stat = {'settled': True}

    picksave(order_stat,rfn)
    rs_ary["message"] = f'Attempting to settle ({fc} attempts)'
    # + rs_ary["settled"] = order_stat["settled"]    # + * store the result
    # + rs_ary["done_reason"] = order_stat["done_reason"]    # + * store the result
    # + rs_ary["status"] = order_stat["status"]    # + * store the result

    istrue = order_stat["settled"]                   # + * set flag to status
    fc = fc + 1
    # + o.eprint(order_stat)

rs_ary["message"] = f'Settled after {fc} attempt'

o.oprint(json.dumps(rs_ary))                        # + * and send as STDOUT reply