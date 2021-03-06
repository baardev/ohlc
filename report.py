#!/usr/bin/python3.9
import lib_globals as g
import lib_ohlc as o
import logging
import getopt
import sys
from colorama import Fore, Back, Style
from colorama import init
init()

# + ≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡
argv = sys.argv[1:]
try:
    opts, args = getopt.getopt(argv, "-hs:v:", ["help","session=","version=" ])
except getopt.GetoptError as err:
    sys.exit(2)

session_name = ""
version = 1
for opt, arg in opts:
    if opt in ("-h", "--help"):
        print("-s, --session   session name")
        print("-v, --version   version 1 (calc row) or 2 (db sum())")
        sys.exit(0)

    if opt in ("-s", "--session"):
        session_name = arg
    if opt in ("-v", "--version"):
        version=int(arg)
# + ≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡


g.logit = logging
g.logit.basicConfig(
    filename="logs/ohlc.log",
    filemode='a',
    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
    level=o.cvars.get('logging')
)
stdout_handler = g.logit.StreamHandler(sys.stdout)
g.dbc, g.cursor = o.getdbconn()

rs = o.get_running_bal(version=1, session_name=session_name)


print(rs)
