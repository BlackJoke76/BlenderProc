import cv2 as cv
import os
import numpy as np
import random
from concurrent.futures import ThreadPoolExecutor
import argparse
os.environ["OPENCV_IO_ENABLE_OPENEXR"]="1"
parser = argparse.ArgumentParser()
parser.add_argument("filname")
parser.add_argument("data_path")
parser.add_argument("img_path")
args = parser.parse_args()


def image_png(img):
        img[img > 1.0] = 1.0
        img = (255 * img).astype(np.uint8)
        return img

def adjust_brightness(files_rgb):
    files_AB =  "A+B_" + (files_rgb.split('_')[1])
    img_rbg_path = os.path.join(args.data_path, files_rgb)
    img_AB_path = os.path.join(args.data_path, files_AB)

    img_rgb = cv.imread(img_rbg_path, cv.IMREAD_UNCHANGED)
    img_AB = cv.imread(img_AB_path, cv.IMREAD_UNCHANGED)
    img_gray_rgb = cv.cvtColor(img_rgb, cv.COLOR_BGR2GRAY)
    img_gray_AB = cv.cvtColor(img_rgb, cv.COLOR_BGR2GRAY)
    brightness_rgb = img_gray_rgb.mean()
    brightness_AB = img_gray_AB.mean()
    print(brightness_rgb)

    if(brightness_rgb < 0.01 or brightness_AB < 0.01):
        return

    png_rgb = args.img_path + "origin/" + os.path.splitext(files_rgb)[0] + ".png"
    png_AB = args.img_path + "shadow_free/" + os.path.splitext(files_AB)[0] + ".png"

    cv.imwrite(png_rgb, image_png(img_rgb))
    cv.imwrite(png_AB, image_png(img_AB))

if __name__ == "__main__":
    filename = args.filname
    adjust_brightness(filename)




