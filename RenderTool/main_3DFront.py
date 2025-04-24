import blenderproc as bproc
import argparse
import os
import numpy as np
import random
import bpy
import mathutils
from mathutils import Matrix
import json
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

def add_a_new_light(light_objs, cur_ceils, hit_location):
    
    index = random.uniform(0, len(light_objs) - 1)
    light_obj = light_objs[int(index)]
    new_obj = light_obj.duplicate()
    light_box = get_bound_min_max_cord(new_obj.get_bound_box())
    cur_box =get_bound_min_max_cord(cur_ceils[0].get_bound_box())

    for ceil in cur_ceils:
        box = get_bound_min_max_cord(ceil.get_bound_box())
        if(box[5] > cur_box[5]):
            cur_box = box

    location_z = cur_box[5] - (light_box[5] - light_box[4]) 

    location = None
    bvh_cache: Dict[str, mathutils.bvhtree.BVHTree] = {}
    other_obj = [mesh for mesh in loaded_objects if "ceil" not in mesh.get_name().lower()]
    ceils = [mesh for mesh in loaded_objects if "Ceiling" in mesh.get_name() and "Lamp" not in mesh.get_name()]
    ceils = [obj for obj in ceils if get_bound_min_max_cord(obj.get_bound_box())[4] > 0.5]
    no_collision = False

    # Generates a position around the intersection of the camera's optical axis and the scene
    i = 0
    while i < 1000:
        
        no_collision = False
        location = disk(
        center=[hit_location[0], hit_location[1], 2],
        radius=2.5,
        sample_from="disk"
        )
        if(bproc.camera.is_point_inside_camera_frustum(location, 0.01, 1000)):
            i += 1
            continue

        # Because the ceiling is composed of multiple layers of mesh
        for ceil in cur_ceils:
            if (ceil.position_is_above_object(location,[0 ,0 ,1], check_no_objects_in_between=False)):
                new_obj.set_location([location[0], location[1], location_z])

                if new_obj.get_name() in bvh_cache:
                    del bvh_cache[new_obj.get_name()]

                no_collision = CollisionUtility.check_intersections(new_obj, bvh_cache, other_obj, other_obj)
                    
                if no_collision:
                    break

        if no_collision:
            break

        i += 1
    # If no suitable location is found, a new location is generated at the center of the current highest ceiling.
    if(not no_collision):
        i = 0
        while i < 1000:
            no_collision = False
            location = disk(
            center=[(cur_box[0] + cur_box[1]) / 2, (cur_box[2] + cur_box[3]) / 2, 2],
            radius=2,
            sample_from="disk"
            )
            if(bproc.camera.is_point_inside_camera_frustum(location, 0.01, 1000)):
                i += 1
                continue
            for ceil in cur_ceils:
                if (ceil.position_is_above_object(location, [0 ,0 ,1], check_no_objects_in_between=False)):
                    new_obj.set_location([location[0], location[1], location_z])

                    if new_obj.get_name() in bvh_cache:
                        del bvh_cache[new_obj.get_name()]

                    no_collision = CollisionUtility.check_intersections(new_obj, bvh_cache, other_obj, other_obj)
                        
                    if no_collision:
                        break

            if no_collision:
                break

            i = i + 1

    # If no suitable location is found, the light is deleted and None is returned.
    if no_collision == False:
        new_obj.delete(True)
        return None
    

    # From the ceiling, from top to bottom, make sure don't hit the ceiling
    i = 0
    while i < 100:
        if new_obj.get_name() in bvh_cache:
            del bvh_cache[new_obj.get_name()]
        new_obj.set_location([location[0], location[1], location_z])
        no_collision = CollisionUtility.check_intersections(new_obj, bvh_cache, ceils, ceils)
        
        if no_collision:
            break
        location_z = location_z - 0.01
        i = i + 1

    if no_collision == False:
        return None


    new_obj.set_location([location[0], location[1], location_z+0.3])
    new_obj.set_scale(mathutils.Vector([1, 1, 1]))
    new_obj.clear_materials()
    new_obj.add_material(light_obj.get_materials()[0].duplicate())
    if obj.blender_obj.rotation_mode == 'QUATERNION':
        new_obj.blender_obj.matrix_world = mathutils.Matrix.LocRotScale(new_obj.blender_obj.location, new_obj.blender_obj.rotation_quaternion, new_obj.blender_obj.scale)
    else:
        new_obj.blender_obj.matrix_world = mathutils.Matrix.LocRotScale(new_obj.blender_obj.location, new_obj.blender_obj.rotation_euler, new_obj.blender_obj.scale)
    return new_obj

def load_light():
    model_home = args.future_folder
    light_jid = ["d2f151e6-1233-4b56-b228-c1fbae3b8549"]
    light_models = []

    for ele in light_jid:
        model_path = os.path.join(model_home, ele)
        model_path = model_path + "/raw_model.obj"
        light_models.append(load_obj(model_path)[0])
        return light_models

def cal_distance(obj1, obj2):
    location1 = obj1.get_location()
    location2 = obj2.get_location()
    distance = ((location1[0] - location2[0]) ** 2 + (location1[1] - location2[1]) ** 2 + (location1[2] - location2[2]) ** 2) ** 0.5
    return distance
def get_fit_light_intensity(obj, lights, lights_count, hit_position, cur_ceil_box):
    #Define standard brightness
    intensity_standard = 2000
    intensity = intensity_standard

    ## Adjust brightness based on surface area
    area = obj.surface_area()
    intensity_adjustment_factor = 1
    if area < 2.22 or area > 4:
        intensity_adjustment_factor = 2.218 / area
        intensity = intensity_adjustment_factor * intensity_standard

    ## Adjust brightness based on height
    height_above_base = obj.get_location()[2] - 2.0
    if height_above_base > 0:
        intensity += (height_above_base * intensity_adjustment_factor * intensity_standard / 2)

    ## Adjust brightness based on number of light sources
    if lights_count > 1:
        min_distance = 100
        for other_obj in lights:
            if obj != other_obj:
                distance = cal_distance(obj, other_obj)
                if 0 < distance < 3:
                    min_distance = min(min_distance, distance)

        ## Adjust brightness based on minimum distance between light sources
        if min_distance != 100:
            distance_adjustment = (4 - min_distance + 2.5) / 6.5
            intensity -= distance_adjustment * (2.218 / area * intensity_standard)
            minimum_intensity = 2.218 / area * (intensity_standard / lights_count)
            intensity = max(intensity, minimum_intensity)

    ## Adjust brightness according to ceiling size
    else:
        box_width = cur_ceil_box[1] - cur_ceil_box[0]
        box_height = cur_ceil_box[3] - cur_ceil_box[2]
        if box_width > 6 or box_height > 6:
            intensity *= 2
        elif box_width < 3 and box_height < 3:
            intensity *= 0.75

    ## Adjust the final brightness based on the distance of the hit location
    distance_to_hit = cal_distance((obj.get_location()[0] - hit_position[0]) ** 2 +
                       (obj.get_location()[1] - hit_position[1]) ** 2 +
                       (obj.get_location()[2] - hit_position[2]) ** 2) ** 0.5
    intensity /= distance_to_hit

    return intensity

    
def get_hit_position(cam2world_matrix):
    transformation_matrix = Matrix(cam2world_matrix)

    camera_object = bpy.context.scene.camera
    camera_data = camera_object.data

    corner_points = camera_data.view_frame(scene=bpy.context.scene)
    world_space_corners = [transformation_matrix @ point for point in corner_points]

    horizontal_vector = world_space_corners[1] - world_space_corners[0]
    vertical_vector = world_space_corners[3] - world_space_corners[0]
    plane_center = world_space_corners[0] + 0.5 * horizontal_vector + 0.5 * vertical_vector

    camera_position = transformation_matrix.to_translation()

    ray_direction = plane_center - camera_position

    _, hit_position, _, _, _, _ = bpy.context.scene.ray_cast(
        bpy.context.evaluated_depsgraph_get(), camera_position, ray_direction)

    return hit_position


parser = argparse.ArgumentParser()
camera_home = '/home/disk1/Dataset/3D_Front_Dataset/camera4/'


parser.add_argument("front", help="Path to the 3D front file")
parser.add_argument("GPU", type=int, help="the index of GPU")
parser.add_argument("-future_folder" ,default='/home/disk1/Dataset/3D_Front_Dataset/3D-FUTURE-model', help="Path to the 3D Future Model folder.")
parser.add_argument("-front_3D_texture_path" ,default='/home/disk1/Dataset/3D_Front_Dataset/3D-FRONT-texture', help="Path to the 3D FRONT texture folder.")
parser.add_argument("-output_dir" ,default='/home/disk5/lzl/render_data/512_hdf/', help="Path to where the data should be saved")
parser.add_argument('-cc_material_path', default="/home/disk1/Dataset/CC_texture_complete", help="Path to CCTextures folder, see the /scripts for the download script.")
parser.add_argument('-cc_material_part_path', default="/home/disk1/Dataset/CC_texture_part", help="Path to CCTextures folder, see the /scripts for the download script.")
args = parser.parse_args()
print('-------------------------------------------------------------')

camera_path = os.path.join(camera_home, args.front.split('/')[-1])
if not os.path.exists(args.front):
    print(args.front)
    raise Exception("front does not exist!")
if not os.path.exists(args.future_folder):
    print(args.future_folder)
    raise Exception("future does not exist!")
if not os.path.exists(camera_path):
    print(camera_path)
    raise Exception("camera does not exist!")

bproc.init()

# get the id of each class of object
mapping_file = bproc.utility.resolve_resource(os.path.join("front_3D", "3D_front_mapping.csv"))
mapping = bproc.utility.LabelIdMapping.from_csv(mapping_file)


# set the light bounces
bproc.renderer.set_render_devices(desired_gpu_ids=[args.GPU])
bproc.renderer.set_output_format("OPEN_EXR")
bproc.renderer.set_max_amount_of_samples(128)
bpy.context.scene.cycles.preview_samples = 10
bpy.context.scene.cycles.use_preview_denoising = True

bpy.context.scene.sequencer_colorspace_settings.name = 'Linear'

# remove the background light, because it will influence the transpaent picture
bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[1].default_value = 0
# load the front 3D objects
loaded_objects, room_bound_2Dbox = bproc.loader.load_front3d(
    json_path=args.front,
    future_model_path=args.future_folder,
    front_3D_texture_path=args.front_3D_texture_path,
    label_mapping=mapping
)

cc_materials = bproc.loader.load_ccmaterials(args.cc_material_path, ["WoodFloor", "Carpet", "Tile", "Marble", "Wallpaper"])


floors = bproc.filter.by_attr(loaded_objects, "name", "Floor.*", regex=True)
floors_mat = random.choice(cc_materials)

for floor in floors:
    # because some light's is Floor_lamp or Floor_light, so we should skip these objects
    if "lamp" in floor.get_name().lower() or "light" in floor.get_name().lower():
        continue
    # For each material of the object
    for i in range(len(floor.get_materials())):
    #     # In 95% of all cases
        if np.random.uniform(0, 1) <= 0.99:
            # Replace the material with a random one
            floor.set_material(i, floors_mat)


baseboards_and_doors = bproc.filter.by_attr(loaded_objects, "name", "Baseboard.*|Door.*", regex=True)
wood_floor_materials = bproc.filter.by_cp(cc_materials, "asset_name", "WoodFloor.*", regex=True)
for obj in baseboards_and_doors:
    # For each material of the object
    for i in range(len(obj.get_materials())):
        # Replace the material with a random one
        obj.set_material(i, random.choice(wood_floor_materials))

walls = bproc.filter.by_attr(loaded_objects, "name", "Wall.*", regex=True)
marble_materials = bproc.filter.by_cp(cc_materials, "asset_name", "Marble.*", regex=True)
wallPaper_materials = bproc.filter.by_cp(cc_materials, "asset_name", "Wallpaper.*", regex=True)
for mat in marble_materials:
    node = mat.get_the_one_node_with_type("ShaderNodeDisplacement")
    mat.remove_node(node)

wall_materail = wallPaper_materials + marble_materials
for wall in walls:
    if "lamp" in floor.get_name().lower() or "light" in floor.get_name().lower():
        continue
    # For each material of the object
    for i in range(len(wall.get_materials())):
        # In 50% of all cases
        if np.random.uniform(0, 1) >= 0.1:
            # Replace the material with a random one
            wall.set_material(i, random.choice(wall_materail))

# # Init bvh tree containing all mesh objects
bvh_tree = bproc.object.create_bvh_tree_multi_objects([o for o in loaded_objects if isinstance(o, bproc.types.MeshObject)])

camera_loactions = []
camera_rotations = []

# add point_light
point_light = bproc.types.Light()
point_light.set_type("POINT")
point_light.set_energy(100)
point_light.blender_obj.data.shadow_soft_size = 0.2
point_light.blender_obj.data.use_nodes = True
point_light_mat = point_light.get_materials()


# add area_light
# area_lights = []
# for i in range(2):
#     light = bproc.types.Light()
#     light.set_type("AREA")
#     light.blender_obj.data.use_nodes = True
#     area_lights.append(light)



with open(camera_path) as f:
    camera_info = json.load(f)

for info in camera_info:
    camera_loactions.append(info['location'])
    camera_rotations.append(info['rotation'])


render_time = len(camera_loactions)
for i in range(0, render_time):
    location = camera_loactions[i]
    rotation = camera_rotations[i]

    cam2world_matrix = bproc.math.build_transformation_mat(location, rotation)
    bproc.camera.set_intrinsics_from_K_matrix(
        [[886.81001348    ,  0.0,                512],
        [0.0,                 886.81001348   ,   512],
        [0.0,                 0.0,                1.0]]
        , 1024, 1024
    )


    bproc.camera.add_camera_pose(cam2world_matrix)

    # get the hit position of the ray which origin is camera and the dierction is the camera's direction
    hit_position = get_hit_position(cam2world_matrix)

    # get all ceiling object
    cur_ceil = None
    ceil_objs = [mesh for mesh in loaded_objects if "Ceiling" in mesh.get_name() and "Lamp" not in mesh.get_name()]
    # because some ceiling is so strange
    ceil_objs = [obj for obj in ceil_objs if get_bound_min_max_cord(obj.get_bound_box())[4] > 0.5]

    # get the ceiling object which camera in
    for ceil in ceil_objs:
        if(ceil.position_is_above_object(location, [0, 0, 1], check_no_objects_in_between=False)):
            cur_ceil = ceil
            break
    
    if(cur_ceil == None):
        continue
        
    cur_ceils = []

    for ceil in ceil_objs:
        if(ceil.get_cp("room") == cur_ceil.get_cp("room")):
            cur_ceils.append(ceil)

    lights = []
    count_dict = []
    lights_count = 0
    # Get all light source objects that meet the conditions
    for obj in get_all_mesh_objects():
        name = obj.get_name()
        obj_location = obj.get_location()
        if (("lamp" in name.lower() or "lighting" in name.lower() \
            or "others" in name.lower()) and obj_location[2] > 1.5):
                for ceil in cur_ceils:
                    if(ceil.position_is_above_object([obj_location[0], obj_location[1], obj_location[2] - 0.1], [0, 0, 1], check_no_objects_in_between=False)):
                        if abs(obj_location[0] - hit_position[0]) <= 2.5 and abs(obj_location[1] - hit_position[1]) <= 2.5:
                            lights.append(obj)
                            break


    # Count the number of light sources that meet the conditions 
    # to avoid repeated counting of light sources in the same group
    for obj in lights:
        if(obj.has_cp("my_parent")):
            if(obj.get_cp("my_parent") in count_dict):
                continue
            else:
                count_dict.append(obj.get_cp("my_parent"))
                lights_count += 1
        else:
            lights_count +=1


    new_light = None
    if(lights_count == 0):
        light_models = load_light()
        new_light = add_a_new_light(light_models, cur_ceils, hit_position)
        # because it wll create light model in the scene
        for model in light_models:
            model.delete(True)

        if(new_light != None):
            lights.append(new_light)
                
                
    if(len(lights) == 0):
        continue
    cur_ceil_box = get_bound_min_max_cord(cur_ceil.get_bound_box())
    is_ceil_light = False
    for obj in lights:
        light_location = obj.get_location()
        if(light_location[2] > 1.5):
            is_ceil_light = True
            point_light.set_location(disk(
            center=lights[0].get_location(),
            radius=0.3,
            sample_from="circle"
            ), i)
            break
    
    if(is_ceil_light == False):
        point_light.set_location(disk(
        center=location,
        radius=0.3,
        sample_from="circle"
        ), i)
    


    # ============add_area_light
    # for light in area_lights: 
    #     for tries in range(2000):
    #         sample_location = bproc.sampler.upper_region(
    #                     objects_to_sample_on=[cur_ceil],
    #                     face_sample_range=[-0.9, 0.9],
    #                     min_height=0.05,
    #                     max_height=0.1,
    #                     use_ray_trace_check=False,
    #                     upper_dir = [0.0, 0.0, -1.0]
    #                 )
    #         if(cur_ceil.position_is_above_object(sample_location, down_direction=[0, 0, 1], check_no_objects_in_between=False) and not bproc.camera.is_point_inside_camera_frustum(sample_location, 0.01, 1000)):
    #             light.set_location(sample_location, i)
    #             break

    #     cur_ceil_box = get_bound_min_max_cord(cur_ceil.get_bound_box())
        
        
    #     light.blender_obj.data.size = random.uniform(0.1, 0.5)
    #     # Compute rotation based on vector going from location towards poi
    #     direction = hit_position - Vector(light.get_location())
    #     direction[0] += random.uniform(-1, 1)
    #     direction[1] += random.uniform(-1, 1)
    #     direction[2] += random.uniform(-1, 1)
    #     rotation_matrix = bproc.camera.rotation_from_forward_vec(direction)
    #     light.set_rotation_mat(rotation_matrix)
    
    #     distance = ((light.get_location()[0] - hit_position[0]) ** 2 + (light.get_location()[1] - hit_position[1]) ** 2 + (light.get_location()[2] - hit_position[2]) ** 2) ** 0.5
    #     light.set_energy(60 * distance / 1.8, i)


# direct shadow-------------------------------------
    for obj in lights:
        intensity = get_fit_light_intensity(obj, lights, lights_count, hit_position, cur_ceil_box)
        mat = obj.get_materials()[0]
        mat.make_emissive(intensity, False, [1.0, 1.0, 1.0, 1.0])


    bproc.renderer.set_light_bounces(diffuse_bounces=200, glossy_bounces=200, max_bounces=0,
                                transmission_bounces=200, transparent_max_bounces=200)
    bproc.renderer.render(file_prefix='direct_sh_', output_key='direct_sh', load_keys={'origin', 'direct_sh', 'direct', 'indirect_sh', 'indirect'})


# direct shadow-free-------------------------------------
    for obj in get_all_mesh_objects():
        if obj not in lights:
            mat = obj.get_materials()[0]
            mat.make_transparent()
    bproc.renderer.set_light_bounces(diffuse_bounces=200, glossy_bounces=200, max_bounces=0,
                                    transmission_bounces=200, transparent_max_bounces=200)
    bproc.renderer.render(file_prefix="direct_", output_key='direct', load_keys={'origin', 'direct_sh', 'direct', 'indirect_sh', 'indirect'})



# indirect shadow-------------------------------------
    for obj in get_all_mesh_objects():
        mat = obj.get_materials()[0]
        mat.remove_transparent()
        if obj in lights:
            intensity = get_fit_light_intensity(obj, lights, lights_count, hit_position, cur_ceil_box)
            mat.make_light_indirect_effect(intensity, [1.0, 1.0, 1.0, 1.0])

    point_light_mat.make_point_light_indirect_effect()

    # for light in area_lights:
    #     light.get_materials().make_point_light_indirect_effect()
    bproc.renderer.set_light_bounces(diffuse_bounces=200, glossy_bounces=200, max_bounces=200,
                                    transmission_bounces=200, transparent_max_bounces=200)
    bproc.renderer.render(file_prefix="indirect_sh_", output_key='indirect_sh', load_keys={'origin', 'direct_sh', 'direct', 'indirect_sh', 'indirect'})


# indirect shadow-free------------------------------------------------
    def check_name(name):
        for category_name in ["Wall", "Ceil", "Floor", "BayWindow", "Slab", "LightBand", "Pocket", "Platform"]:
            if category_name in name:
                return False
        return True

    for obj in get_all_mesh_objects():
        mat = obj.get_materials()[0]
        if obj not in lights:
            if(check_name(obj.get_name())):
                mat.make_indirect_effect_v2()


    bproc.renderer.set_light_bounces(diffuse_bounces=200, glossy_bounces=200, max_bounces=200,
                    transmission_bounces=200, transparent_max_bounces=200)
    data = bproc.renderer.render(file_prefix="indirect_", output_key='indirect', load_keys={'origin', 'direct_sh', 'direct', 'indirect_sh', 'indirect'})
    # write the data to a .hdf5 container
    bproc.writer.write_hdf5(args.output_dir, data, True)
# -----------------------------------------------
    for obj in get_all_mesh_objects():
        mat = obj.get_materials()[0]
        mat.remove_transparent()
        mat.remove_emissive()
        mat.remove_indirect_effect_v2()



    if(new_light != None):
        new_light.delete(True)

    point_light_mat.remove_point_light_indirect_effect()
    # for light in area_lights:
    #     light.get_materials().remove_point_light_indirect_effect()

    # Eliminate the current frame to avoid rendering next
    # time Render two pictures at a time, because it does 
    # not remove the camera coordinates added last time
    bproc.utility.reset_keyframes()
    print(args.front)