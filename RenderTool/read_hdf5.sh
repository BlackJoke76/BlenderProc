#!/bin/bash

MAX_CONCURRENT=8
hdf5_path="/home/disk5/lzl/render_data/512_hdf/"
output_path="/home/disk5/lzl/render_data/test_data/"
start=`date +%s`

mkfifo tm1
exec 5<>tm1
rm -f tm1

for((i = 0; i < $MAX_CONCURRENT; ++i))
do
    echo >&5
done

echo "begin the program"

i=0
for file in `ls $hdf5_path`
    do
        ((i++))
        echo $i
        read -u5   
        {
            echo "$i begin"
            python ./read_hdf5.py $file $hdf5_path $output_path
            echo >&5
        }&

        
    done

wait
exec 5>&-
exec 5<&-

end=`date +%s`
time=$(($end - $start))
echo "time: $time"

