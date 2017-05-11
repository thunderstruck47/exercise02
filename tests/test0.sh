#!/bin/bash
##  A script to collect data for and plot persistent vs non-persistent
##  connections performance (responses per second) for the Bistro server

## Create CSV file
today=`date '+%Y_%m_%d__%H_%M_%S'`;
duration="10s"
filename="test0_$duration-$today"

## File headers
echo "Concurrency,RPS(Persistent connections),RPS(Nonpersistent connections)" >> data/$filename.csv

## BASE CASE:
## RPS persistent (keep-alive):
rpsPC=`ab -c 1 -t $duration -k http://0.0.0.0:8000/ | grep 'Requests per second' | awk '{print $4}'`;

sleep 1s

## RPS nonpersistent:
rpsNPC=`ab -c 1 -t $duration http://0.0.0.0:8000/ | grep 'Requests per second' | awk '{print $4}'`;

sleep 1s

## Add to result
echo "1,$rpsPC,$rpsNPC" >> data/$filename.csv

## REST:
for ((x=100; x<=1000; x+=100));
do
    ## RPS persistent (keep-alive):
    rpsPC=`ab -c $x -t $duration -k http://0.0.0.0:8000/ | grep 'Requests per second' | awk '{print $4}'`;

    sleep 5s

    ## RPS nonpersistent:
    rpsNPC=`ab -c $x -t $duration http://0.0.0.0:8000/ | grep 'Requests per second' | awk '{print $4}'`;

    ## Add to result
    echo "$x,$rpsPC,$rpsNPC" >> data/$filename.csv
    sleep 5s
done

## Gnuplot config and plotting
printf "set title 'Responses per Second: Persistent vs Nonpersistent Connections'
set datafile separator ','
set xlabel 'Concurrency'
set ylabel 'RPS'
set grid
set term png
set key autotitle columnhead
set output 'plots/$filename.png'
plot 'data/$filename.csv' using 1:2 with lines, '' using 1:3 with lines" > tmp
gnuplot tmp
rm tmp
