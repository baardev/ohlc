#!/usr/bin/python3.9
import time


while True:
    epoch_time = int(time.time())
    t5 = epoch_time % 300
    if t5==0:
        print("---------------------------------------------------------")
    print(epoch_time, t5)

    time.sleep(1)