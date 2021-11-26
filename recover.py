#!/usr/bin/python3.9
import matplotlib
import logging
matplotlib.use('Tkagg')
import lib_globals as g
import lib_ohlc as o
import getopt, sys, os

# + ≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡

argv = sys.argv[1:]
try:
    opts, args = getopt.getopt(argv, "-hd:", ["help","dir="])
except getopt.GetoptError as err:
    sys.exit(2)

g.session_name = False
dir = False
for opt, arg in opts:
    if opt in ("-h", "--help"):
        print("-h, --help   this info")
        print("-d, --dir  dir of run")
        sys.exit(0)

    if opt in ("-d", "--dir"):
        dir = arg

if not dir:
    print("Missinfg dir (-d)")
    exit(1)

# + ≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡

print(f"RECOVERING: {dir}")


g.logit = logging
g.logit.basicConfig(
    filename="logs/ohlc.log",
    filemode='a',
    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
    level=o.cvars.get('logging')
)
stdout_handler = g.logit.StreamHandler(sys.stdout)

os.chdir(f"../{dir}")

g.session_name = o.state_r("session_name")

cmd = f"./dbview.py -s {g.session_name} -c profit &"
print(cmd)
os.system(cmd)


cmd = f"cd ../{dir} && ./ohlc.py -r "
print(cmd)
os.system(cmd)



