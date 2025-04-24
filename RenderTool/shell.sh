#!/bin/bash

MAX_CONCURRENT=4
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
        echo $i
        # if [ "$i" -lt 2000 ]; then
        #     continue
        # fi

        # if [ "$i" -ge 100 ]; then
        #     break
        # fi
        read -u5   
        {
            echo "$i begin"
            echo $file
            index=`expr $i % 4`
            echo $index
            blenderproc run /home/lzl/code/python/main.py $Front_Path"/"$file $index
            echo >&5
            sleep 5
        }&

    done

wait
exec 5>&-
exec 5<&-

end=`date +%s`
time=$(($end - $start))
echo "time: $time"




