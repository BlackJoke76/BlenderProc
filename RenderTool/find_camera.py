import blenderproc as bproc
import argparse
import os
import numpy as np
import random
import bpy
import mathutils
import json
import cv2 as cv
import time
from typing import Dict
from blenderproc.python.types.MeshObjectUtility import get_all_mesh_objects
from blenderproc.python.sampler.Disk import disk
from blenderproc.python.loader.ObjectLoader import load_obj
from blenderproc.python.utility.CollisionUtility import CollisionUtility


def get_bound_min_max_cord(bbox):
        x_min = np.min(bbox[:, 0])
        x_max = np.max(bbox[:, 0])
        y_min = np.min(bbox[:, 1])
        y_max = np.max(bbox[:, 1])
        z_min = np.min(bbox[:, 2])
        z_max = np.max(bbox[:, 2])
        return  [x_min, x_max, y_min, y_max, z_min, z_max]



parser = argparse.ArgumentParser()
camera_home = '/home/disk1/Dataset/3D_Front_Dataset/camera4/'

parser.add_argument("front", help="Path to the 3D front file")
parser.add_argument("-future_folder" ,default='/home/disk1/Dataset/3D_Front_Dataset/3D-FUTURE-model', help="Path to the 3D Future Model folder.")
parser.add_argument("-front_3D_texture_path" ,default='/home/disk1/Dataset/3D_Front_Dataset/3D-FRONT-texture', help="Path to the 3D FRONT texture folder.")
parser.add_argument("-output_dir" ,default='/home/disk5/lzl/render_data/512_hdf/', help="Path to where the data should be saved")
args = parser.parse_args()
camera_path = os.path.join(camera_home, args.front.split('/')[-1])


if not os.path.exists(args.front) or not os.path.exists(args.future_folder):
    raise Exception("One of the two folders does not exist!")
bproc.init()
mapping_file = bproc.utility.resolve_resource(os.path.join("front_3D", "3D_front_mapping.csv"))
print(mapping_file)
mapping = bproc.utility.LabelIdMapping.from_csv(mapping_file)

# load the front 3D objects
loaded_objects, room_bound_2Dbox = bproc.loader.load_front3d(
    json_path=args.front,
    future_model_path=args.future_folder,
    front_3D_texture_path=args.front_3D_texture_path,
    label_mapping=mapping
)


furnituers = []
count_dict = []
for obj in loaded_objects:
    if(obj.has_cp("my_parent")):
        if(obj.get_cp("my_parent") in count_dict):
            continue
        else:
            count_dict.append(obj.get_cp("my_parent"))
            furnituers.append(obj)
    else:
        furnituers.append(obj)

# # Init sampler for sampling locations inside the loaded front3D house
point_sampler = bproc.sampler.Front3DPointInRoomSampler(furnituers)

# # Init bvh tree containing all mesh objects
bvh_tree = bproc.object.create_bvh_tree_multi_objects([o for o in loaded_objects if isinstance(o, bproc.types.MeshObject)])
print(camera_path)

def check_name(name):
    for category_name in ["chair", "sofa", "table", "desk", "floor-based",
                          "bed", "recreation", "tv", "storage unit"]:
        if category_name in name.lower():
            return True
    return False

def check_name_dont_want(name):
    for category_name in ["pendant", "ceiling lamp", "ceiling light"]:
        if category_name in name.lower():
            return True
    return False

# filter some objects from the loaded objects, which are later used in calculating an interesting score
special_objects = [obj.get_cp("category_id") for obj in loaded_objects if check_name(obj.get_name())]
special_objects_dont_want = [obj.get_cp("category_id") for obj in loaded_objects if check_name_dont_want(obj.get_name())]

proximity_checks = {"min": 1.0, "avg": {"min": 1.5, "max": 5}, "no_background": True}


locations = []
rotations = []
camera_matrix = []
bproc.renderer.enable_segmentation_output(map_by=["category_id"])
render_time = 4
floor_objs = [mesh for mesh in loaded_objects if "floor" in mesh.get_name().lower() and "Lamp" not in mesh.get_name()]


for i in range(0, render_time):
    poses = 0
    tries = 0
    location = None
    rotation = None
    find = False
    while tries < 3000 and poses < 1:
        # Sample point inside house

        height = np.random.uniform(1.2, 1.8)
        location = point_sampler.sample(height)
        
        # Sample rotation (fix around X and Y axis)
        rotation = np.random.uniform([1.2217, 0, 0], [1.338, 0, np.pi * 2])

        cam2world_matrix = bproc.math.build_transformation_mat(location, rotation)
        bproc.camera.set_intrinsics_from_K_matrix(
            [[443.40500674    ,  0.0,                128],
            [0.0,                 443.40500674   ,   128],
            [0.0,                 0.0,                1.0]]
            , 256, 256
        )
        # Check that obstacles are at least 1 meter away from the camera and have an average distance between 2.5 and 3.5
        # meters and make sure that no background is visible, finally make sure the view is interesting enough

        ceil_objs = [mesh for mesh in loaded_objects if "Ceiling" in mesh.get_name() and "Lamp" not in mesh.get_name()]
        ceil_objs = [obj for obj in ceil_objs if get_bound_min_max_cord(obj.get_bound_box())[4] > 0.5]

        for ceil in ceil_objs:
            if(ceil.position_is_above_object(location, [0, 0, 1], check_no_objects_in_between=False)):
                cur_ceil = ceil
                break
            
        if bproc.camera.scene_coverage_score(cur_ceil, cam2world_matrix, special_objects, special_objects_dont_want, sqrt_number_of_rays=40):
            bproc.camera.add_camera_pose(cam2world_matrix)
            camera_matrix.append(cam2world_matrix)
            find = True

            poses += 1

        tries += 1


    if(find == False):
        continue
    
    locations.append(location)
    rotations.append(rotation)


camera_info = []
with open(camera_path, 'w+') as f:
    for i in range(0, len(locations)):
        loc = locations[i].tolist()
        rot = rotations[i].tolist()
        camera_info_pair = {'location': loc, 'rotation': rot}
        camera_info.append(camera_info_pair)
    json.dump(camera_info, f, indent=4)

print(f"{args.front} finish find")