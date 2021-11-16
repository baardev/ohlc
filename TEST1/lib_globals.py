datasetname = "noname"
datawindow = False
verbose = False
buyfiltername = ""
sellfiltername = ""
instance_num = 0
can_load = True
ohlc = False
cfgfile = f"config_{instance_num}.hcl"
statefile = f"state_{instance_num}.json"
interval = 0
state = False
time_to_die = False
cursor = False
dbc = False
session_name = "noname"
df_buysell = False
df_allrecords = False
avg_price = float("Nan")
conversion = 60000
spot_src = False
ticker_src = False
last_conversion = conversion
subtot_value = float("Nan")
subtot_qty = float("Nan")
subtot_cost = float("Nan")
subtot_sold = float("Nan")
curr_qty = float("Nan")
curr_cost = float("Nan")
current_run_count = 0
purch_qty = False  # ! loaded in main from cvars  (min amount for CB = 0.01)
purch_qty_adj_pct = False  # ! loaded in main from cvars
# purch_qty_adj_qty = False  # ! loaded in main from cvars
capital = 1
purch_pct = 0.1

pct_gain_list = []
pnl_record_list = []
pct_record_list = []

last_pct_gain = float("Nan")
last_pnl_record = float("Nan")
last_pct_record = float("Nan")

pct_return = 0
pct_cap_return = 0

pnl_running = float("Nan")
pct_running = float("Nan")

sell_mark = float("Nan")
idx = 0
gcounter = 0
pt1 = 0
previous_point = 0
prev_md5 = 0
batchmode = False
num_axes = 6
time_start = 0
time_end = 0
run_time = 0
curr_buys = 0
tot_buys = 0
tot_sells = 0
buys_permitted = True
external_buy_signal = False
external_sell_signal = False
is_first_buy = True
wordlabel = "unnamed"
autoclear = False
cooldown = 0
last_close = 0
this_close = 0


# ! these are the only fields allowed for the coinbase order(s), as determined by 'cb_order.py'
cflds = {
    'type': "--type",
    'side': "--side",
    'pair': "--pair",
    'size': "--size",
    'price': "--price",
    'stop_price': "--stop_price",
    'upper_stop_price': "--upper_stop_price",
    'funds': "--funds",
    'uid': "--uid"
}

ansi = {
    # 'xxxx': '\u001b[30m'  # + black
    # ,'xxxx': '\u001b[31m'     # + red
    'INFO': '\u001b[32m',  # + green
    # ,'xxxx': '\u001b[33m'  # + yellow
    # ,'xxxx': '\u001b[34m'    # + blue
    # ,'xxxx': '\u001b[35m' # + magenta
    # ,'xxxx': '\u001b[36m'    # + cyan
    # ,'xxxx': '\u001b[37m'   # + white
    'reset': '\u001b[0m'  # + reset
}

logit = False

_siglft = []

# * general global place to store things
bag = {
    "siglft": [],
    "sigfft": [],

    "sigfft0": [],
    "sigfft1": [],
    "sigfft2": [],
    "sigfft3": [],
    "sigfft4": [],
    "sigfft5": [],

    "sigfft20": [],
    "sigfft21": [],
    "sigfft22": [],
    "sigfft23": [],
    "sigfft24": [],
    "sigfft25": []
}
cwd = "."
