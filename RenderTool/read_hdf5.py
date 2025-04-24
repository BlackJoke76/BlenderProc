import os
import h5py
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import cv2
import argparse
os.environ["OPENCV_IO_ENABLE_OPENEXR"]="1"

parser = argparse.ArgumentParser()
parser.add_argument("hdf5")
parser.add_argument("hdf5_folder")
parser.add_argument("output_folder")
args = parser.parse_args()


with h5py.File(os.path.join(args.hdf5_folder, args.hdf5), "r") as f:
    if "origin" in f:
        origin = np.array(f["origin"])
        cv2.imwrite(os.path.join(args.output_folder, 'rgb_' + os.path.splitext(args.hdf5)[0] + ".exr"), origin[:,:, ::-1].astype(np.float32))

    if "direct" in f:
        direct = np.array(f["direct"])
        direct = direct[:,:, ::-1]

    if "indirect" in f:
        indirect = np.array(f["indirect"])
        indirect = indirect[:,:, ::-1]

    if "indirect_sh" in f:
        indirect_sh = np.array(f["indirect_sh"])
        indirect_sh = indirect_sh[:,:, ::-1]

    if "direct_sh" in f:
        direct_sh = np.array(f["direct_sh"])
        direct_sh = direct_sh[:,:, ::-1]

    img_rgb = (direct_sh + indirect_sh).astype(np.float32)
    img_AB = (direct + indirect).astype(np.float32)
    cv2.imwrite(os.path.join(args.output_folder, 'rgb_' + os.path.splitext(args.hdf5)[0] + ".exr"), img_rgb)
    cv2.imwrite(os.path.join(args.output_folder, 'A+B_' + os.path.splitext(args.hdf5)[0] + ".exr"), img_AB) 

