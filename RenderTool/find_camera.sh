#!/bin/bash

MAX_CONCURRENT=128
Front_Path="/home/disk1/Dataset/3D_Front_Dataset/3D-FRONT3"
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
for file in `ls $Front_Path`
    do
        ((i++))
        # if [ "$i" -lt 4550 ]; then
        #     continue
        # fi
        read -u5   
        {
            echo "$i begin"
            blenderproc run ./find_camera.py "$Front_Path"/"$file"
            echo >&5
            echo “$i finished”
            
        }&

    done

wait
exec 5>&-
exec 5<&-

end=`date +%s`
time=$(($end - $start))
echo "time: $time"




