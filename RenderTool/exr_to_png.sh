#!/bin/bash

MAX_CONCURRENT=128
data_path="/home/disk5/lzl/render_data/test_data/"
png_path="/home/disk5/lzl/render_data/test_png/"
start=`date +%s`

mkfifo tm1
exec 5<>tm1
rm -f tm1

for((i = 0; i < $MAX_CONCURRENT; ++i))
do
    echo >&5
done

echo "begin the program"

# count=0

# for file in `ls $data_path`
#     do
#         ((count++))
#     done

# count=$((count / 2))
# for((i=0; i<=$count; i++));
#     do
#     # if [ "$i" -le 3364 ]; then
#     #     continue
#     # fi
#     # if [ "$i" -ge 5000 ]; then
#     #     break
#     # fi
#     read -u5   
#     {

#         echo "$i begin"
#         python ./correct_brightness.py $i $data_path $png_path 
#         echo >&5
        
#     }&
# done

i=0
files=$(ls "$data_path" | grep "^rgb")
for file in $files
    do
    read -u5   
    {

        echo "$file begin"
        python ./exr_to_png.py $file $data_path $png_path 
        echo >&5
        
    }&
done


wait
exec 5>&-
exec 5<&-

end=`date +%s`
time=$(($end - $start))
echo "time: $time"

