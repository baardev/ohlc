#!/bin/bash
while [ 1 ]
do
ps -A --sort -rss -o pid,comm,pmem,rss|grep ohlc
done
