#!/bin/bash

MAX_CONCURRENT=128
EXR_Path="/home/disk5/lzl/render_data/test_data"
Input_Color_Space="Linear"
Output_Color_Space="Filmic_sRGB"
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

# for file in `ls $EXR_Path`
#     do
#         ((count++))
#     done

# count=$((count / 2))

# for((i=0; i<=$count; i++));
#     do
#         # if [ "$i" -le 24000 ]; then
#         #     continue
#         # fi
#         # if [ "$i" -ge 24500 ]; then
#         #     break
#         # fi
#         read -u5   
#         {
#             ocioconvert $EXR_Path"/rgb_${i}.exr" $Input_Color_Space $EXR_Path"/rgb_${i}.exr" $Output_Color_Space
#             ocioconvert $EXR_Path"/A+B_${i}.exr" $Input_Color_Space $EXR_Path"/A+B_${i}.exr" $Output_Color_Space
#             echo >&5
            
#         }&
#     done


for file in `ls $EXR_Path`
    do
        ocioconvert $EXR_Path"/"$file $Input_Color_Space $EXR_Path"/"$file $Output_Color_Space
    done


            

wait
exec 5>&-
exec 5<&-

end=`date +%s`
time=$(($end - $start))
echo "time: $time"

