import blenderproc as bproc
import argparse
import numpy as np
import bpy
import random
import os
import json
import mathutils
from math import radians
from blenderproc.python.types.MeshObjectUtility import get_all_mesh_objects, convert_to_meshes
from typing import Union, List, Set
from collections import defaultdict
from mathutils import Matrix


# Define a function that samples the pose of a given object
def sample_pose(obj: bproc.types.MeshObject, last_obj):
    # Sample the spheres location above the surface
    last_location = [0,0,0]
    if(last_obj != None):
        last_location = last_obj.get_location()
    obj.set_location(
    bproc.sampler.disk(
        center=last_location,
        radius=1.2,
        sample_from="disk"
    ))
    obj.blender_obj.location[2] = random.uniform(2,4)
    obj.blender_obj.rotation_euler[2] = np.random.uniform(0, np.pi * 2)

def get_all_files(folder_path):
    all_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            all_files.append(file_path)
        for subdir in dirs:
            subdir_path = os.path.join(root, subdir)
            all_files.extend(get_all_files(subdir_path))  # 递归调用
    return all_files


parser = argparse.ArgumentParser()
parser.add_argument('camera', nargs='?', default="/home/lzl/BlenderProc/examples/resources/camera_positions", help="Path to the camera file")
parser.add_argument('-cc_material_path', default="/home/disk1/Dataset/CC_texture", help="Path to CCTextures folder, see the /scripts for the download script.")
parser.add_argument('output_dir', nargs='?', default="/home/disk5/lzl/render_data/objectreverse_hdf", help="Path to where the final files will be saved ")
parser.add_argument("json", help="Path to the json file")
parser.add_argument("gpu", type=int)
args = parser.parse_args()

bproc.init()
bproc.renderer.set_render_devices(desired_gpu_ids=[args.gpu])
bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[1].default_value = 0
bproc.renderer.set_output_format("OPEN_EXR")
bpy.context.scene.sequencer_colorspace_settings.name = 'Linear'
bproc.renderer.set_max_amount_of_samples(128)



def sample_camera(special_objects):
    # Sample location
    
    # camera where to see

    special_blenderobj = []
    for ele in special_objects:
        special_blenderobj.append(ele.blender_obj)


    tries = 0
    while tries < 100:

        poi = bproc.object.compute_poi(np.random.choice(special_objects, size=2)) 
        # Determine point of interest in scene as the object closest to the mean of a subset of objects
        location = bproc.sampler.shell(center = poi,
                                radius_min = 1.5,
                                radius_max = 4.0,
                                elevation_min = 5,
                                elevation_max = 65,
                                uniform_volume = False)

        # Compute rotation based on vector going from location towards poi
        rotation_matrix = bproc.camera.rotation_from_forward_vec(poi - location)
        
        
        
        cam2world_matrix = bproc.math.build_transformation_mat(location, rotation_matrix)
        bproc.camera.set_intrinsics_from_K_matrix(
        [[886.81001348    ,  0.0,                512],
        [0.0,                 886.81001348   ,   512],
        [0.0,                 0.0,                1.0]]
        , 1024, 1024
        )
        # bproc.camera.set_intrinsics_from_K_matrix(
        #     [[443.40500674    ,  0.0,                256],
        #     [0.0,                 443.40500674   ,   256],
        #     [0.0,                 0.0,                1.0]]
        #     , 512, 512
        # )

        if scene_coverage_score(cam2world_matrix, special_blenderobj, sqrt_number_of_rays=40):
            bproc.camera.add_camera_pose(cam2world_matrix)
            break
        tries += 1

def scene_coverage_score(cam2world_matrix: Union[Matrix, np.ndarray], special_objects: list = None, sqrt_number_of_rays: int = 10) -> bool:

    cam2world_matrix = Matrix(cam2world_matrix)

    cam_ob = bpy.context.scene.camera
    cam = cam_ob.data

    num_of_rays = sqrt_number_of_rays * sqrt_number_of_rays
    objects_hit: defaultdict = defaultdict(int)

    # Get position of the corners of the near plane
    frame = cam.view_frame(scene=bpy.context.scene)
    # Bring to world space
    frame = [cam2world_matrix @ v for v in frame]

    # Compute vectors along both sides of the plane
    vec_x = frame[1] - frame[0]
    vec_y = frame[3] - frame[0]

    # count_cur_floor = 0
    # Go in discrete grid-like steps over plane
    position = cam2world_matrix.to_translation()
    camera_center = frame[0] + vec_x * 0.5 + vec_y * 0.5
    _, hit_position, _, _, hit_object, _ = bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(),
                                                                    position, camera_center - position)

    distance_center_camera = ((position[0] - hit_position[0]) ** 2 + (position[1] - hit_position[1]) ** 2 + (position[2] - hit_position[2]) ** 2) ** 0.5
    

    if(distance_center_camera >= 5 or distance_center_camera <= 1.0):
        return False


    for x in range(0, sqrt_number_of_rays):
        for y in range(0, sqrt_number_of_rays):
            # Compute current point on plane
            end = frame[0] + vec_x * x / float(sqrt_number_of_rays - 1) + vec_y * y / float(sqrt_number_of_rays - 1)
            # Send ray from the camera position through the current point on the plane
            _, _, _, _, hit_object, _ = bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(),
                                                                    position, end - position)

            objects_hit[hit_object] += 1



    total = num_of_rays
    count_want = 0
    for ele in special_objects:
        if(objects_hit[ele] / total > 0.25):
            print("big want")
            return False

        count_want += objects_hit[ele]

    if(count_want / total < 0.15):
        print("small want")
        return False
    
    return True

def load_and_process_mesh(model_path, resize):
    if model_path.lower().endswith('.glb') or model_path.lower().endswith('.gltf'):
        bpy.ops.import_scene.gltf(filepath=model_path)

    elif model_path.endswith(".obj"):
        bpy.ops.wm.obj_import(filepath=model_path)
        blender_rot_mat = mathutils.Matrix.Rotation(radians(90), 4, 'X')

    objs = [obj for obj in bpy.context.selected_objects]
    meshes = [obj for obj in objs if obj.type == 'MESH']

    # If the meshes list is not empty, select all mesh objects and merge them
    if meshes:
        bpy.ops.object.select_all(action='DESELECT')  
        for obj in meshes:
            obj.select_set(True)  
        bpy.context.view_layer.objects.active = meshes[0]  
        bpy.ops.object.join()  

    mesh = bpy.context.object
    parent = mesh.parent

    matrix_world = mesh.matrix_basis
    parents =[]
    while parent is not None:
        parents.append(parent)
        parent = parent.parent
        
    for parent in parents:
        matrix_world = parent.matrix_basis @ parent.matrix_parent_inverse @ matrix_world

    mesh.parent = None
    mesh.matrix_basis = matrix_world


    if resize:
        max_axis = max(mesh.dimensions)
        max_value = random.uniform(0.5, 1)
        scale = max_value / max_axis
        mesh.scale *= scale 


    mesh.rotation_mode = 'XYZ'
    mesh = convert_to_meshes([mesh])[0]

    if(model_path.endswith(".obj")):
        mesh.set_rotation_euler(blender_rot_mat.to_euler())
        mats = mesh.get_materials()
        for mat in mats:
            principled_node = mat.get_nodes_with_type("BsdfPrincipled")
            principled_node[0].inputs["Transmission"].default_value = 0.0
            principled_node[0].inputs["Roughness"].default_value = 0.4
            principled_node[0].inputs["Specular"].default_value = 0.4
    # mesh.set_origin(mode="CENTER_OF_GEOMETRY")

    return mesh
    

# load the objects into the scene

select_objects = []
with open(args.json, "r", encoding="utf-8") as json_file:
    select_objects = json.load(json_file)






# load material
cc_materials = bproc.loader.load_ccmaterials(args.cc_material_path)


# create room
room_planes = [bproc.object.create_primitive('PLANE', scale=[10, 10, 1]),
               bproc.object.create_primitive('PLANE', scale=[10, 10, 1], location=[0, -10, 10], rotation=[-1.570796, 0, 0]),
               bproc.object.create_primitive('PLANE', scale=[10, 10, 1], location=[0, 10, 10], rotation=[1.570796, 0, 0]),
               bproc.object.create_primitive('PLANE', scale=[10, 10, 1], location=[10, 0, 10], rotation=[0, -1.570796, 0]),
               bproc.object.create_primitive('PLANE', scale=[10, 10, 1], location=[-10, 0, 10], rotation=[0, 1.570796, 0])]

surface = room_planes[0]

objects = []
for obj in select_objects:
    print(obj)
    obj_model = load_and_process_mesh(obj["path"], obj["resize"])
    if(obj_model.blender_obj.dimensions.z < 0.05):
        continue

    objects.append(obj_model)

floors_mat = random.choice(cc_materials)
marble_materials = random.choice(bproc.filter.by_cp(cc_materials, "asset_name", "Marble.*", regex=True)).duplicate()

# remove displacement
node = marble_materials.get_the_one_node_with_type("ShaderNodeDisplacement")
marble_materials.remove_node(node)

surface.replace_materials(floors_mat)
# set scale to let texture fit plane'size
node = surface.get_materials()[0].get_the_one_node_with_type("Mapping")
#resolution of texture
node.inputs[3].default_value[0] = 4
node.inputs[3].default_value[1] = 4
node.inputs[3].default_value[2] = 4

for plane in room_planes[1:]:
    plane.replace_materials(marble_materials)
    # set scale to let texture fit plane'size
    node = marble_materials.get_the_one_node_with_type("Mapping")
    node.inputs[3].default_value[0] = 4
    node.inputs[3].default_value[1] = 4
    node.inputs[3].default_value[2] = 4


# Sample the position on the surface
objects = bproc.object.sample_poses_on_surface(objects, surface, sample_pose, min_distance=0.1, max_distance=2)

# Enable physics for obj (active) and the surface (passive)
for object in objects:
    object.enable_rigidbody(True)
surface.enable_rigidbody(False)


print("------------------------------------------------------------")
for obj in select_objects:
    print(obj)

# Run the physics simulation
bproc.object.simulate_physics_and_fix_final_poses(min_simulation_time=2, max_simulation_time=5, check_object_interval=1)

if(random.random() > 0.7):
    z = random.uniform(0.4, 1)
    fly_model = random.sample(objects, 1)
    fly_model[0].blender_obj.location[2] += z


bop_bvh_tree = bproc.object.create_bvh_tree_multi_objects(objects)


poses = 0
while poses < 3:
    sample_camera(objects)
    poses += 1




lights = []
# Area light
AreaLight_Count = random.randint(1,2)
for i in range(AreaLight_Count):
    light = bproc.types.Light()
    light.set_type("AREA")
    light.set_location(bproc.sampler.upper_region(
            objects_to_sample_on=[surface],
            face_sample_range=[-0.9, 0.9],
            min_height=8,
            max_height=10,
            use_ray_trace_check=False
        ))
    light.set_energy(random.randint(800, 1000))
    light.blender_obj.data.size = random.uniform(0.1, 0.5)
    # Determine point of interest in scene as the object closest to the mean of a subset of objects
    poi = bproc.object.compute_poi(np.random.choice(objects, size=5))
    # Compute rotation based on vector from location towards poi
    direction = poi - light.get_location()
    direction[0] += random.uniform(-1, 1)
    direction[1] += random.uniform(-1, 1)
    direction[2] += random.uniform(-1, 1)
    rotation_matrix = bproc.camera.rotation_from_forward_vec(direction)
    light.set_rotation_mat(rotation_matrix)
    light.blender_obj.data.use_nodes = True
    lights.append(light)

# point light
PointLight_Count = random.randint(1,2)
for i in range(PointLight_Count):
    light = bproc.types.Light()
    light.set_type("POINT")
    light.set_location(bproc.sampler.upper_region(
            objects_to_sample_on=[surface],
            face_sample_range=[-0.9, 0.9],
            min_height=6,
            max_height=8,
            use_ray_trace_check=False
        ))
    light.set_energy(random.randint(800, 1200))
    light.set_radius(radius=random.uniform(0, 0.5))
    light.blender_obj.data.use_nodes = True
    lights.append(light)


# direct shadow
bproc.renderer.set_light_bounces(diffuse_bounces=200, glossy_bounces=200, max_bounces=0,
                            transmission_bounces=200, transparent_max_bounces=200)
bproc.renderer.render(file_prefix='direct_sh_', output_key='direct_sh', load_keys={'origin', 'direct_sh', 'direct', 'indirect_sh', 'indirect'})


# direct shadow_free
for obj in get_all_mesh_objects():
    if obj not in lights:
        for mat in obj.get_materials():
            mat.make_transparent()
bproc.renderer.set_light_bounces(diffuse_bounces=200, glossy_bounces=200, max_bounces=0,
                                transmission_bounces=200, transparent_max_bounces=200)
bproc.renderer.render(file_prefix="direct_", output_key='direct', load_keys={'origin', 'direct_sh', 'direct', 'indirect_sh', 'indirect'})


# indirect shadow
for obj in get_all_mesh_objects():
    for mat in obj.get_materials():
        mat.remove_transparent()

for light in lights:
    light.get_materials().make_point_light_indirect_effect()
bproc.renderer.set_light_bounces(diffuse_bounces=200, glossy_bounces=200, max_bounces=200,
                                transmission_bounces=200, transparent_max_bounces=200)
bproc.renderer.render(file_prefix="indirect_sh_", output_key='indirect_sh', load_keys={'origin', 'direct_sh', 'direct', 'indirect_sh', 'indirect'})

# indirect shadow_free
def check_name(name):
    for category_name in ["plane"]:
        if category_name in name:
            return False
    return True
for obj in get_all_mesh_objects():
    for mat in obj.get_materials():
        if(check_name(obj.get_name())):
            mat.make_indirect_effect_v2()
bproc.renderer.set_light_bounces(diffuse_bounces=200, glossy_bounces=200, max_bounces=200,
                transmission_bounces=200, transparent_max_bounces=200)

data = bproc.renderer.render(file_prefix="indirect_", output_key='indirect', load_keys={'origin', 'direct_sh', 'direct', 'indirect_sh', 'indirect'})
bproc.writer.write_hdf5(args.output_dir, data, True)

