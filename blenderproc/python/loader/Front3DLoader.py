"""Loads the 3D FRONT and FUTURE dataset"""

import json
import os
import warnings
from math import radians
from typing import List, Mapping
from urllib.request import urlretrieve

import bpy
import mathutils
import numpy as np
import trimesh
from mathutils import Vector, Matrix

from blenderproc.python.material import MaterialLoaderUtility
from blenderproc.python.utility.LabelIdMapping import LabelIdMapping
from blenderproc.python.utility.CollisionUtility import CollisionUtility
from blenderproc.python.types.MeshObjectUtility import MeshObject, create_with_empty_mesh, get_all_mesh_objects
from blenderproc.python.utility.Utility import resolve_path
from blenderproc.python.loader.ObjectLoader import load_obj
from blenderproc.python.loader.TextureLoader import load_texture
from blenderproc.python.filter.Filter import one_by_attr




def load_front3d(json_path: str, future_model_path: str, front_3D_texture_path: str, label_mapping: LabelIdMapping,
                 ceiling_light_strength: float = 0.0, lamp_light_strength: float = 0.0) -> List[MeshObject]:
    """ Loads the 3D-Front scene specified by the given json file.

    :param json_path: Path to the json file, where the house information is stored.
    :param future_model_path: Path to the models used in the 3D-Front dataset.
    :param front_3D_texture_path: Path to the 3D-FRONT-texture folder.
    :param label_mapping: A dict which maps the names of the objects to ids.
    :param ceiling_light_strength: Strength of the emission shader used in the ceiling.
    :param lamp_light_strength: Strength of the emission shader used in each lamp.
    :return: The list of loaded mesh objects.
    """
    json_path = resolve_path(json_path)
    future_model_path = resolve_path(future_model_path)
    front_3D_texture_path = resolve_path(front_3D_texture_path)

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"The given path does not exists: {json_path}")
    if not json_path.endswith(".json"):
        raise FileNotFoundError(f"The given path does not point to a .json file: {json_path}")
    if not os.path.exists(future_model_path):
        raise FileNotFoundError(f"The 3D future model path does not exist: {future_model_path}")

    # load data from json file
    with open(json_path, "r", encoding="utf-8") as json_file:
        data = json.load(json_file)

    if "scene" not in data:
        raise ValueError(f"There is no scene data in this json file: {json_path}")
    


    created_objects, room_bound_2Dbox = _Front3DLoader.create_mesh_objects_from_file(data, front_3D_texture_path,
                                                                   ceiling_light_strength, label_mapping, json_path)

    all_loaded_furniture  = _Front3DLoader.load_furniture_objs(data, future_model_path,
                                                              lamp_light_strength, label_mapping)

    # all_loaded_furniture = _Front3DLoader.remove_intersection_obj(all_loaded_furniture)


    created_objects += _Front3DLoader.move_and_duplicate_furniture(data, all_loaded_furniture, created_objects)

    # add an identifier to the obj
    for obj in created_objects:
        obj.set_cp("is_3d_front", True)

    return created_objects, room_bound_2Dbox



class _Front3DLoader:
    """ Loads the 3D-Front dataset.

    https://tianchi.aliyun.com/specials/promotion/alibaba-3d-scene-dataset

    Each object gets the name based on the category/type, on top of that you can use a mapping specified in the
    resources/front_3D folder.

    The dataset already supports semantic segmentation with either the 3D-Front classes or the nyu classes.
    As we have created this mapping ourselves it might be faulty.

    The Front3DLoader creates automatically lights in the scene, by adding emission shaders to the ceiling and lamps.
    """

    @staticmethod
    def extract_hash_nr_for_texture(given_url: str, front_3D_texture_path: str) -> str:
        """
        Constructs the path of the hash folder and checks if the texture is available if not it is downloaded

        :param given_url: The url of the texture
        :param front_3D_texture_path: The path to where the texture are saved
        :return: The hash id, which is used in the url
        """
        # extract the hash nr from the given url
        hash_nr = given_url.split("/")[-2]
        hash_folder = os.path.join(front_3D_texture_path, hash_nr)
        if not os.path.exists(hash_folder):
            # download the file
            os.makedirs(hash_folder)
            warnings.warn(f"This texture: {hash_nr} could not be found it will be downloaded.")
            # replace https with http as ssl connection out of blender are difficult
            urlretrieve(given_url.replace("https://", "http://"), os.path.join(hash_folder, "texture.png"))
            if not os.path.exists(os.path.join(hash_folder, "texture.png")):
                raise Exception(f"The texture could not be found, the following url was used: "
                                f"{front_3D_texture_path}, this is the extracted hash: {hash_nr}, "
                                f"given url: {given_url}")
        return hash_folder

    @staticmethod
    def get_used_image(hash_folder_path: str, saved_image_dict: Mapping[str, bpy.types.Texture]) -> bpy.types.Texture:
        """
        Returns a texture object for the given hash_folder_path, the textures are stored in the saved_image_dict,
        to avoid that texture are loaded multiple times

        :param hash_folder_path: Path to the hash folder
        :param saved_image_dict: Dict which maps the hash_folder_paths to bpy.types.Texture
        :return: The loaded texture bpy.types.Texture
        """
        if hash_folder_path in saved_image_dict:
            ret_used_image = saved_image_dict[hash_folder_path]
        else:
            textures = load_texture(hash_folder_path)
            if len(textures) != 1:
                raise Exception(f"There is not just one texture: {len(textures)}")
            ret_used_image = textures[0].image
            saved_image_dict[hash_folder_path] = ret_used_image
        return ret_used_image

    @staticmethod
    def get_bound_min_max_cord(bbox):
        x_min = np.min(bbox[:, 0])
        x_max = np.max(bbox[:, 0])
        y_min = np.min(bbox[:, 1])
        y_max = np.max(bbox[:, 1])
        z_min = np.min(bbox[:, 2])
        z_max = np.max(bbox[:, 2])
        return  [x_min, x_max, y_min, y_max, z_min, z_max]

    @staticmethod
    def create_mesh_objects_from_file(data: dict, front_3D_texture_path: str, ceiling_light_strength: float,
                                      label_mapping: LabelIdMapping, json_path: str) -> List[MeshObject]:
        """
        This creates for a given data json block all defined meshes and assigns the correct materials.
        This means that the json file contains some mesh, like walls and floors, which have to built up manually.
        It also already adds the lighting for the ceiling
        :param data: json data dir. Must contain "material" and "mesh"
        :param front_3D_texture_path: Path to the 3D-FRONT-texture folder.
        :param ceiling_light_strength: Strength of the emission shader used in the ceiling.
        :param label_mapping: A dict which maps the names of the objects to ids.
        :param json_path: Path to the json file, where the house information is stored.
        :return: The list of loaded mesh objects.
        """
        # extract all used materials -> there are more materials defined than used
        used_materials = []
        for mat in data["material"]:
            used_materials.append({"uid": mat["uid"], "texture": mat["texture"],
                                   "normaltexture": mat["normaltexture"], "color": mat["color"]})

        created_objects = []
        # maps loaded images from image file path to bpy.type.image
        saved_images = {}
        saved_normal_images = {}
        # materials based on colors to avoid recreating the same material over and over
        used_materials_based_on_color = {}
        # materials based on texture to avoid recreating the same material over and over
        used_materials_based_on_texture = {}
        for mesh_data in data["mesh"]:
            # extract the obj name, which also is used as the category_id name
            used_obj_name = mesh_data["type"].strip()
            if used_obj_name == "":
                used_obj_name = "void"
            if "material" not in mesh_data:
                warnings.warn(f"Material is not defined for {used_obj_name} in this file: {json_path}")
                continue
            # create a new mesh
            obj = create_with_empty_mesh(used_obj_name, used_obj_name + "_mesh")
            created_objects.append(obj)

            # set two custom properties, first that it is a 3D_future object and second the category_id
            obj.set_cp("is_3D_future", True)
            obj.set_cp("category_id", label_mapping.id_from_label(used_obj_name.lower()))
            obj.set_cp("uid", mesh_data["uid"] )

            # get the material uid of the current mesh data
            current_mat = mesh_data["material"]
            used_mat = None
            # search in the used materials after this uid
            for u_mat in used_materials:
                if u_mat["uid"] == current_mat:
                    used_mat = u_mat
                    break
            # If there should be a material used
            if used_mat:
                if used_mat["texture"]:
                    # extract the has folder is from the url and download it if necessary
                    hash_folder = _Front3DLoader.extract_hash_nr_for_texture(used_mat["texture"], front_3D_texture_path)
                    if hash_folder in used_materials_based_on_texture and "ceiling" not in used_obj_name.lower():
                        mat = used_materials_based_on_texture[hash_folder]
                        obj.add_material(mat)
                    else:
                        # Create a new material
                        mat = MaterialLoaderUtility.create(name=used_obj_name + "_material")
                        principled_node = mat.get_the_one_node_with_type("BsdfPrincipled")
                        if used_mat["color"]:
                            principled_node.inputs["Base Color"].default_value = mathutils.Vector(
                                used_mat["color"]) / 255.0

                        used_image = _Front3DLoader.get_used_image(hash_folder, saved_images)
                        mat.set_principled_shader_value("Base Color", used_image)

                        if "ceiling" in used_obj_name.lower():
                            mat.make_emissive(ceiling_light_strength,
                                              emission_color=mathutils.Vector(used_mat["color"]) / 255.0)

                        if used_mat["normaltexture"]:
                            # get the used image based on the normal texture path
                            # extract the has folder is from the url and download it if necessary
                            hash_folder = _Front3DLoader.extract_hash_nr_for_texture(used_mat["normaltexture"],
                                                                                     front_3D_texture_path)
                            used_image = _Front3DLoader.get_used_image(hash_folder, saved_normal_images)

                            # create normal texture
                            normal_texture = MaterialLoaderUtility.create_image_node(mat.nodes, used_image, True)
                            normal_map = mat.nodes.new("ShaderNodeNormalMap")
                            normal_map.inputs["Strength"].default_value = 1.0
                            mat.links.new(normal_texture.outputs["Color"], normal_map.inputs["Color"])
                            # connect normal texture to principled shader
                            mat.set_principled_shader_value("Normal", normal_map.outputs["Normal"])

                        obj.add_material(mat)
                        used_materials_based_on_texture[hash_folder] = mat
                # if there is a normal color used
                elif used_mat["color"]:
                    used_hash = tuple(used_mat["color"])
                    if used_hash in used_materials_based_on_color and "ceiling" not in used_obj_name.lower():
                        mat = used_materials_based_on_color[used_hash]
                    else:
                        # Create a new material
                        mat = MaterialLoaderUtility.create(name=used_obj_name + "_material")
                        # create a principled node and set the default color
                        principled_node = mat.get_the_one_node_with_type("BsdfPrincipled")
                        principled_node.inputs["Base Color"].default_value = mathutils.Vector(used_mat["color"]) / 255.0
                        # if the object is a ceiling add some light output
                        if "ceiling" in used_obj_name.lower():
                            mat.make_emissive(ceiling_light_strength,
                                              emission_color=mathutils.Vector(used_mat["color"]) / 255.0)
                        else:
                            used_materials_based_on_color[used_hash] = mat

                    # as this material was just created the material is just append it to the empty list
                    obj.add_material(mat)

            # extract the vertices from the mesh_data
            vert = [float(ele) for ele in mesh_data["xyz"]]
            # extract the faces from the mesh_data
            faces = mesh_data["faces"]
            # extract the normals from the mesh_data
            normal = [float(ele) for ele in mesh_data["normal"]]

            # map those to the blender coordinate system
            num_vertices = int(len(vert) / 3)
            vertices = np.reshape(np.array(vert), [num_vertices, 3])
            normal = np.reshape(np.array(normal), [num_vertices, 3])
            # flip the first and second value
            vertices[:, 1], vertices[:, 2] = vertices[:, 2], vertices[:, 1].copy()
            normal[:, 1], normal[:, 2] = normal[:, 2], normal[:, 1].copy()
            # reshape back to a long list
            vertices = np.reshape(vertices, [num_vertices * 3])
            normal = np.reshape(normal, [num_vertices * 3])

            # add this new data to the mesh object
            mesh = obj.get_mesh()
            mesh.vertices.add(num_vertices)
            mesh.vertices.foreach_set("co", vertices)
            mesh.vertices.foreach_set("normal", normal)

            # link the faces as vertex indices
            num_vertex_indicies = len(faces)
            mesh.loops.add(num_vertex_indicies)
            mesh.loops.foreach_set("vertex_index", faces)

            # the loops are set based on how the faces are a ranged
            num_loops = int(num_vertex_indicies / 3)
            mesh.polygons.add(num_loops)
            # always 3 vertices form one triangle
            loop_start = np.arange(0, num_vertex_indicies, 3)
            # the total size of each triangle is therefore 3
            loop_total = [3] * num_loops
            mesh.polygons.foreach_set("loop_start", loop_start)
            mesh.polygons.foreach_set("loop_total", loop_total)

            # the uv coordinates are reshaped then the face coords are extracted
            uv_mesh_data = [float(ele) for ele in mesh_data["uv"] if ele is not None]
            # bb1737bf-dae6-4215-bccf-fab6f584046b.json includes one mesh which only has no UV mapping
            if uv_mesh_data:
                uv = np.reshape(np.array(uv_mesh_data), [num_vertices, 2])
                used_uvs = uv[faces, :]
                # and again reshaped back to the long list
                used_uvs = np.reshape(used_uvs, [2 * num_vertex_indicies])

                mesh.uv_layers.new(name="new_uv_layer")
                mesh.uv_layers[-1].data.foreach_set("uv", used_uvs)
            else:
                warnings.warn(f"This mesh {obj.get_name()} does not have a specified uv map!")

            # this update converts the upper data into a mesh
            mesh.update()

            # the generation might fail if the data does not line up
            # this is not used as even if the data does not line up it is still able to render the objects
            # We assume that not all meshes in the dataset do conform with the mesh standards set in blender
            # result = mesh.validate(verbose=False)
            # if result:
            #    raise Exception("The generation of the mesh: {} failed!".format(used_obj_name))

        # return created_objects

        
        # for getting the bbox of every room, but if the floor isn`t a square ,the bbox may be not precision
        for _, room in enumerate(data["scene"]["room"]):
            for child in room["children"]:
                if "mesh" in child["instanceid"]:
                    for obj in created_objects:
                        if obj.get_cp("uid") == child["ref"]:
                            name = obj.get_name()
                            if "ceiling" in name.lower():
                                obj.set_cp("room", room["instanceid"])
        
        room_bound_2Dbox = []
        for _,room in enumerate(data["scene"]["room"]):
            # if 'other' in room["instanceid"].lower():
            #     continue

            min_x = 100
            max_x = -100
            min_y = 100
            max_y = -100
            z = 0
            for obj in created_objects:
                if obj.has_cp("room"):
                    if obj.get_cp("room") == room["instanceid"]:
                        box = _Front3DLoader.get_bound_min_max_cord(obj.get_bound_box())
                        # print(box)
                        min_x = box[0] if min_x > box[0] else min_x
                        min_y = box[2] if min_y > box[2] else min_y

                        max_x = box[1] if max_x < box[1] else max_x
                        max_y = box[3] if max_y < box[3] else max_y

                        z = box[5]
            room_bound_2Dbox.append([min_x, max_x, min_y, max_y, z])
            # print('--------------------')
        
        # because a bug that walls are emission
        for obj in created_objects:
            obj.clear_materials()
            mat = MaterialLoaderUtility.create(name=used_obj_name + "_material")
            if("ceil" not in obj.get_name().lower()):
                BSDF_Node = mat.get_the_one_node_with_type('BsdfPrincipled')
                BSDF_Node.inputs['Base Color'].default_value = [0.6, 0.6, 0.6, 1]



            obj.add_material(mat)

        return created_objects, room_bound_2Dbox

    @staticmethod
    def load_furniture_objs(data: dict, future_model_path: str, lamp_light_strength: float,
                            label_mapping: LabelIdMapping) -> List[MeshObject]:
        """
        Load all furniture objects specified in the json file, these objects are stored as "raw_model.obj" in the
        3D_future_model_path. For lamp the lamp_light_strength value can be changed via the config.

        :param data: json data dir. Should contain "furniture"
        :param future_model_path: Path to the models used in the 3D-Front dataset.
        :param lamp_light_strength: Strength of the emission shader used in each lamp.
        :param label_mapping: A dict which maps the names of the objects to ids.
        :return: The list of loaded mesh objects.
        """
        # collect all loaded furniture objects
        all_objs = []
        # for each furniture element

        left_list = []
        for i in range(0, len(data["furniture"])):
            if(data["furniture"][i] not in left_list):
                left_list.append(data["furniture"][i])

        data["furniture"] = left_list.copy()
        
        parents_count = 0
        for ele in data["furniture"]:
            # create the paths based on the "jid"
            if(ele["jid"].lower().endswith('.glb')):
                ABO_model_path = "/home/disk2/zqh/LEGO-Net/LEGO-Net_test1/ABO_dataset/ABO_livingroom"
                obj_file = os.path.join(ABO_model_path, ele["jid"])
                objs = load_obj(filepath=obj_file)

                used_obj_name = ""
                if "category" in ele:
                    used_obj_name = ele["category"]
                elif "title" in ele:
                    used_obj_name = ele["title"]
                    # if "/" in used_obj_name:
                    #     used_obj_name = used_obj_name.split("/")[0]
                if used_obj_name == "" or used_obj_name == None:
                    used_obj_name = "others"

                objs.set_name(used_obj_name)
                # add some custom properties
                objs.set_cp("uid", ele["uid"])
                # this custom property determines if the object was used before
                # is needed to only clone the second appearance of this object
                objs.set_cp("is_used", False)
                objs.set_cp("is_3D_future", True)
                objs.set_cp("3D_future_type", "Non-Object")  # is an non object used for the interesting score
                # set the category id based on the used obj name
                objs.set_cp("category_id", label_mapping.id_from_label(used_obj_name.lower()))
                objs.set_cp("is_ABO", True)
                all_objs.append(objs)

            else:
                folder_path = os.path.join(future_model_path, ele["jid"])
                obj_file = os.path.join(folder_path, "raw_model.obj")

                # folder_path = os.path.join(future_model_path, ele["jid"])
                # obj_file = os.path.join(future_model_path, ele["jid"])
                # here should be normalized_model, otherwize some model will very huge in the blender scene 
                # obj_file = os.path.join(folder_path, "normalized_model.obj")
                # if the object exists load it -> a lot of object do not exist
                # we are unsure why this is -> we assume that not all objects have been made public
                if os.path.exists(obj_file) and not "7e101ef3-7722-4af8-90d5-7c562834fabd" in obj_file:
                    # load all objects from this .obj file
                    objs = load_obj(filepath=obj_file)

                    # this means ABO
                    if(not isinstance(objs, list)):
                        objs = [objs]

                    used_obj_name = ""
                    if "category" in ele:
                        used_obj_name = ele["category"]
                    elif "title" in ele:
                        used_obj_name = ele["title"]
                        # if "/" in used_obj_name:
                        #     used_obj_name = used_obj_name.split("/")[0]
                    if used_obj_name == "" or used_obj_name == None:
                        used_obj_name = "others"

                    if(len(objs) > 1):
                        parents_count = parents_count + 1

                    for obj in objs:
                        obj.set_name(used_obj_name)
                        # add some custom properties
                        obj.set_cp("uid", ele["uid"])
                        # this custom property determines if the object was used before
                        # is needed to only clone the second appearance of this object
                        obj.set_cp("is_used", False)
                        obj.set_cp("is_3D_future", True)
                        obj.set_cp("3D_future_type", "Non-Object")  # is an non object used for the interesting score
                        # set the category id based on the used obj name
                        obj.set_cp("category_id", label_mapping.id_from_label(used_obj_name.lower()))


                        # 设置parent
                        if(len(objs) > 1):
                            obj.set_cp('my_parent', used_obj_name + "parent" + str(parents_count))
                        # print(type(obj))
                        # walk over all materials
                        if(not ele["jid"].lower().endswith('.glb')):
                            for mat in obj.get_materials():
                                if mat is None:
                                    continue
                                principled_node = mat.get_nodes_with_type("BsdfPrincipled")
                                principled_node[0].inputs["Transmission"].default_value = 0.0
                                if "bed" in used_obj_name.lower() or "sofa" in used_obj_name.lower():
                                    if len(principled_node) == 1:
                                        principled_node[0].inputs["Roughness"].default_value = 0.5

                                elif "lamp" not in used_obj_name.lower() and "light" not in used_obj_name.lower():
                                    if len(principled_node) == 1:
                                        principled_node[0].inputs["Roughness"].default_value = 0.2

                                is_lamp = "lamp" in used_obj_name.lower() or "light" in used_obj_name.lower()
                                if len(principled_node) == 0 and is_lamp:
                                    # this material has already been transformed
                                    continue
                                if len(principled_node) == 1:
                                    principled_node = principled_node[0]
                                else:
                                    raise ValueError(f"The amount of principle nodes can not be more than 1, "
                                                    f"for obj: {obj.get_name()}!")

                                # Front3d .mtl files contain emission color which make the object mistakenly emissive
                                # => Reset the emission color
                                principled_node.inputs["Emission"].default_value[:3] = [0, 0, 0]

                                # For each a texture node
                                image_node = mat.new_node('ShaderNodeTexImage')
                                # and load the texture.png
                                base_image_path = os.path.join(folder_path, "texture.png")
                                image_node.image = bpy.data.images.load(base_image_path, check_existing=True)
                                mat.link(image_node.outputs['Color'], principled_node.inputs['Base Color'])
                                # if the object is a lamp, do the same as for the ceiling and add an emission shader
                                # if is_lamp:
                                #     mat.make_emissive(emission_strength = lamp_light_strength, emission_color = [1.0 ,1.0 ,1.0, 1.0])
                                    # mat.make_emissive(lamp_light_strength)
                    all_objs.extend(objs)
                elif "7e101ef3-7722-4af8-90d5-7c562834fabd" in obj_file:
                    warnings.warn(f"This file {obj_file} was skipped as it can not be read by blender.")

        return all_objs


  

                    
        

    @staticmethod
    def move_and_duplicate_furniture(data: dict, all_loaded_furniture: list, mesh_objects: list) -> List[MeshObject]:
        """
        Move and duplicate the furniture depending on the data in the data json dir.
        After loading each object gets a location based on the data in the json file. Some objects are used more than
        once these are duplicated and then placed.

        :param data: json data dir. Should contain "scene", which should contain "room"
        :param all_loaded_furniture: all objects which have been loaded in load_furniture_objs
        :param mesh_objects: the mesh that created by the function create_mesh_objects_from_file
        :return: The list of loaded mesh objects.
        """
        # this rotation matrix rotates the given quaternion into the blender coordinate system
        blender_rot_mat = mathutils.Matrix.Rotation(radians(-90), 4, 'X')
        created_objects = []
        collision_objects = []
        bvh_cache: Dict[str, mathutils.bvhtree.BVHTree] = {}
        # for each room
        for room_id, room in enumerate(data["scene"]["room"]):
            # for each object in that room
            for child in room["children"]:
                if "furniture" in child["instanceid"]:
                    # find the object where the uid matches the child ref id
                    # value count is used to find the parent of meshs 
                    count = 0
                    parent = ''
                    for obj in all_loaded_furniture:
                        if obj.get_cp("uid") == child["ref"]:
                            # if the object was used before, duplicate the object and move that duplicated obj
                            if obj.get_cp("is_used"):
                                new_obj = obj.duplicate()
                                new_obj.clear_materials()
                                new_obj.add_material(obj.get_materials()[0].duplicate())
                    


                                if(new_obj.has_cp('my_parent')):
                                    if(count == 0):
                                        parent = new_obj.get_name()
                                        count = 1

                                    new_obj.set_cp('my_parent', parent)
                                else:
                                    count = 0
                            else:
                                # if it is the first time use the object directly
                                new_obj = obj

                            if(new_obj.has_cp("is_ABO") == True):
                                bbox = new_obj.get_bound_box()
                                new_obj.set_origin((bbox[0] + bbox[7]) / 2)

                            created_objects.append(new_obj)
                            new_obj.set_cp("is_used", True)
                            new_obj.set_cp("room_id", room_id)
                            new_obj.set_cp("3D_future_type", "Object")  # is an object used for the interesting score
                            new_obj.set_cp("coarse_grained_class", new_obj.get_cp("category_id"))
                            # this used to move thing munnully
                            new_obj.set_cp("instanceid", child['instanceid'])
                            # this flips the y and z coordinate to bring it to the blender coordinate system
                            child["pos"][1] += -0.00005
                            new_obj.set_location(mathutils.Vector(child["pos"]).xzy)
                            # new_obj.set_scale(child["scale"])
                            new_obj.set_scale(mathutils.Vector(child["scale"]).xyz)

                            # this is right, and you nedd to use it after ...
                            # new_obj.set_scale(mathutils.Vector(child["scale"]).xzy)
                            # extract the quaternion and convert it to a rotation matrix
                            rotation_mat = mathutils.Quaternion(child["rot"]).to_euler().to_matrix().to_4x4()

                            new_obj.blender_obj.rotation_mode = 'XYZ'
                            # transform it into the blender coordinate system and then to an euler
                            if(new_obj.has_cp("is_ABO") == True):
                                # new_obj.set_rotation_euler((blender_rot_mat @ rotation_mat).to_euler())
                                euler = (blender_rot_mat @ rotation_mat).to_euler()
                                euler[0] = 0
                                new_obj.set_rotation_euler(euler)
                            else:
                                new_obj.set_rotation_euler((blender_rot_mat @ rotation_mat).to_euler())

                                
                            # if(new_obj.has_cp("is_ABO") == True):
                                
                            
                            # used for scene which has ABO
                            # if not CollisionUtility.check_intersections(new_obj, bvh_cache, created_objects, []):
                            #     step = 0.05
                            #     same_obj = []
                            #     for ele in created_objects:
                            #         if(ele.has_cp("my_parent") and ele.get_cp("my_parent") != new_obj.get_cp("my_parent")):
                            #             collision_objects.append(ele)
                                    
                            #         if(not ele.has_cp("my_parent")):
                            #             collision_objects.append(ele)

                            #         if(ele.has_cp("my_parent") and ele.get_cp("my_parent") == new_obj.get_cp("my_parent")):
                            #             same_obj.append(ele)

                                    

                            #     for i in range(100):
                                    
                            #         new_obj.set_location(mathutils.Vector(((child["pos"])[0] + step, child["pos"][2], child["pos"][1])))
                            #         for ele in same_obj:
                            #             ele.set_location(mathutils.Vector(((child["pos"])[0] + step, child["pos"][2], child["pos"][1])))
                            #         if CollisionUtility.check_intersections(new_obj, bvh_cache, collision_objects, []):
                            #             break

                            #         new_obj.set_location(mathutils.Vector(((child["pos"])[0] - step, child["pos"][2], child["pos"][1])))
                            #         for ele in same_obj:
                            #             ele.set_location(mathutils.Vector(((child["pos"])[0] - step, child["pos"][2], child["pos"][1])))
                            #         if CollisionUtility.check_intersections(new_obj, bvh_cache, collision_objects, []):
                            #             break

                            #         new_obj.set_location(mathutils.Vector(((child["pos"])[0], child["pos"][2] + step, child["pos"][1])))
                            #         for ele in same_obj:
                            #             ele.set_location(mathutils.Vector(((child["pos"])[0], child["pos"][2] + step, child["pos"][1])))
                            #         if CollisionUtility.check_intersections(new_obj, bvh_cache, collision_objects, []):
                            #             break

                            #         new_obj.set_location(mathutils.Vector(((child["pos"])[0], child["pos"][2] - step, child["pos"][1])))
                            #         for ele in same_obj:
                            #             ele.set_location(mathutils.Vector(((child["pos"])[0], child["pos"][2] - step, child["pos"][1])))
                            #         if CollisionUtility.check_intersections(new_obj, bvh_cache, collision_objects, []):
                            #             break

                            #         step += 0.05








        
        # remove_list = []
        # CollisionManager = trimesh.collision.CollisionManager()
        # for obj in created_objects:
        #     if "lighting" in obj.get_name().lower() or "lamp" in obj.get_name().lower():
        #         mesh_data = obj.get_mesh()
        #         local2world = Matrix(obj.get_local2world_mat())
        #         vertices = [local2world @ Vector(v.co) for v in mesh_data.vertices]
        #         faces = []

        #         # 获取面的顶点索引
        #         vertex_indices = mesh_data.polygons[0]

        #         # 检查面是否为三角形
        #         if  len(vertex_indices.vertices) != 3:
        #             continue

        #         for face in mesh_data.polygons:
        #             faces.append([v for v in face.vertices])

        #         trimesh_mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        #         CollisionManager.add_object(obj.get_name(), trimesh_mesh)

        # for obj in mesh_objects:
        #     if('wallouter' in obj.get_name().lower() or 'wallinner' in obj.get_name().lower()):
        #     # if('ceiling' in obj.get_name().lower()):
        #     # if('wallouter' in obj.get_name().lower()):
        #         mesh_data = obj.get_mesh()
        #         local2world = Matrix(obj.get_local2world_mat())
        #         vertices = [local2world @ Vector(v.co) for v in mesh_data.vertices]
        #         faces = []
        #         for face in mesh_data.polygons:
        #             faces.append([v for v in face.vertices])

        #         trimesh_mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        #         CollisionManager.add_object(obj.get_name(), trimesh_mesh)

        # _, names = CollisionManager.in_collision_internal(return_names=True)
        # # print(names)
        # # print('-----------')
        # for name in names:
        #     if("wall" in name[0].lower() and "wall" in name[1].lower()):
        #         continue

        #     elif("wall" in name[0].lower() and "wall" not in name[1].lower()):
        #         mesh = one_by_attr(mesh_objects, "name", name[0])
        #         obj = one_by_attr(created_objects, "name", name[1])



        #         box1 = _Front3DLoader.get_bound_min_max_cord(mesh.get_bound_box())
        #         box2 = _Front3DLoader.get_bound_min_max_cord(obj.get_bound_box())
        #         # print(box1)
        #         # print(box2) 
        #         # print("\n")
                
        #         intersect = (box1[1] > box2[0] + 0.1) and (box1[0] + 0.1 < box2[1]) and\
        #                     (box1[3] > box2[2] + 0.1) and (box1[2] + 0.1 < box2[3]) and\
        #                     (box1[5] > box2[4] + 0.1) and (box1[4] + 0.1 < box2[5])

        #         if(intersect):
        #             remove_list.append(obj)

        #     elif("wall" not in name[0].lower() and "wall" in name[1].lower()):
        #         mesh = one_by_attr(mesh_objects, "name", name[1])
        #         obj = one_by_attr(created_objects, "name", name[0])


        #         box1 = _Front3DLoader.get_bound_min_max_cord(mesh.get_bound_box())
        #         box2 = _Front3DLoader.get_bound_min_max_cord(obj.get_bound_box())
        #         # print(box1)
        #         # print(box2) 
        #         # print("\n")
        #         intersect = (box1[1] > box2[0] + 0.1) and (box1[0] + 0.1 < box2[1]) and\
        #                     (box1[3] > box2[2] + 0.1) and (box1[2] + 0.1 < box2[3]) and\
        #                     (box1[5] > box2[4] + 0.1) and (box1[4] + 0.1 < box2[5])
                                
        #         if(intersect):
        #             remove_list.append(obj)
            
        #     else:
        #         obj1 = one_by_attr(created_objects, "name", name[0])
        #         obj2 = one_by_attr(created_objects, "name", name[1])

        #         if(obj1.has_cp('my_parent') and obj2.has_cp('my_parent') and obj1.get_cp('my_parent') == obj2.get_cp('my_parent')):
        #             # print(name[0])
        #             # print(name[1])
        #             # print(obj1.get_cp('my_parent'))
        #             # print(obj2.get_cp('my_parent'))
        #             # print('------------')
        #             continue

        #         # dont need true in get_bound_box(), mabey program bug
        #         box1 = _Front3DLoader.get_bound_min_max_cord(obj1.get_bound_box())
        #         box2 = _Front3DLoader.get_bound_min_max_cord(obj2.get_bound_box())
        #         # print(box1)
        #         # print(box2)
        #         # print("\n")
        #         intersect = (box1[1] > box2[0] + 0.1) and (box1[0] + 0.1 < box2[1]) and\
        #                     (box1[3] > box2[2] + 0.1) and (box1[2] + 0.1 < box2[3]) and\
        #                     (box1[5] > box2[4] + 0.1) and (box1[4] + 0.1 < box2[5])

        #         if(not intersect):
        #             continue

        #         bbox1_volume = obj1.get_bound_box_volume()
        #         bbox2_volume = obj2.get_bound_box_volume()
        #         if(bbox1_volume > bbox2_volume):
        #             remove_list.append(obj2)

        #         else:
        #             remove_list.append(obj1)


        # for obj in remove_list:
        #     if obj in created_objects:  
        #         created_objects.remove(obj)
        #         obj.delete(True)

        # delete furniture that doesn't have room info
        for obj in get_all_mesh_objects():
            if obj.has_cp("3D_future_type"):
                if obj.get_cp("3D_future_type") == "Non-Object":
                    if obj not in created_objects:
                        obj.delete(True)
                    

        return created_objects
