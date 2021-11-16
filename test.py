#!/usr/bin/python3.9
import time


def is_epoch_boundry(modby):
    epoch_time = int(time.time())
    t5 = epoch_time % modby
    if t5==0:
        return True
    else:
        return False

while True:
    print(is_boundry(300))
    time.sleep(1)