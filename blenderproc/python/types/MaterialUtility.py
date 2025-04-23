""" The material class containing the texture and material properties. """

from typing import List, Union

import bpy

from blenderproc.python.utility import BlenderUtility
from blenderproc.python.types.StructUtility import Struct
from blenderproc.python.utility.Utility import Utility


class Material(Struct):
    """
    The material class containing the texture and material properties, which are assigned to the surfaces
    of MeshObjects.
    """


    def __init__(self, material: bpy.types.Material):
        super().__init__(material)
        if not material.use_nodes:
            raise RuntimeError(f"The given material {material.name} does not have nodes enabled and can "
                               f"therefore not be handled by BlenderProc's Material wrapper class.")

        self.nodes = material.node_tree.nodes
        self.links = material.node_tree.links

    def update_blender_ref(self, name):
        """ Updates the contained blender reference using the given name of the instance.

        :param name: The name of the instance which will be used to update its blender reference.
        """
        self.blender_obj = bpy.data.materials[name]
        self.nodes = bpy.data.materials[name].node_tree.nodes
        self.links = bpy.data.materials[name].node_tree.links

    def get_users(self) -> int:
        """ Returns the number of users of the material.

        :return: The number of users.
        """
        return self.blender_obj.users

    def duplicate(self) -> "Material":
        """ Duplicates the material.

        :return: The new material which is a copy of this one.
        """
        return Material(self.blender_obj.copy())

    def get_the_one_node_with_type(self, node_type: str, created_in_func: str = "") -> bpy.types.Node:
        """ Returns the one node which is of the given node_type

        This function will only work if there is only one of the nodes of this type.

        :param node_type: The node type to look for.
        :param created_in_func: only return node created by the specified function
        :return: The node.
        """
        return Utility.get_the_one_node_with_type(self.nodes, node_type, created_in_func)

    def get_nodes_with_type(self, node_type: str, created_in_func: str = "") -> List[bpy.types.Node]:
        """ Returns all nodes which are of the given node_type

        :param node_type: The note type to look for.
        :param created_in_func: only return nodes created by the specified function
        :return: The list of nodes with the given type.
        """
        return Utility.get_nodes_with_type(self.nodes, node_type, created_in_func)

    def get_nodes_created_in_func(self, created_in_func: str) -> List[bpy.types.Node]:
        """ Returns all nodes which are of the given node_type

        :param created_in_func: return all nodes created in the given function
        :return: The list of nodes with the given type.
        """
        return Utility.get_nodes_created_in_func(self.nodes, created_in_func)

    def new_node(self, node_type: str, created_in_func: str = "") -> bpy.types.Node:
        """ Creates a new node in the material's node tree.

        :param node_type: The desired type of the new node.
        :param created_in_func: Save the function name in which this node was created as a custom property.
                                Allows to later retrieve and delete specific nodes again.
        :return: The new node.
        """
        new_node = self.nodes.new(node_type)
        if created_in_func:
            new_node["created_in_func"] = created_in_func
        return new_node

    def remove_node(self, node: bpy.types.Node):
        """ Removes the node from the material's node tree.

        :param node: The node to remove.
        """
        self.nodes.remove(node)

    def insert_node_instead_existing_link(self, source_socket: bpy.types.NodeSocket,
                                          new_node_dest_socket: bpy.types.NodeSocket,
                                          new_node_src_socket: bpy.types.NodeSocket,
                                          dest_socket: bpy.types.NodeSocket):
        """ Replaces the node between source_socket and dest_socket with a new node.

        Before: source_socket -> dest_socket
        After: source_socket -> new_node_dest_socket and new_node_src_socket -> dest_socket

        :param source_socket: The source socket.
        :param new_node_dest_socket: The new destination for the link starting from source_socket.
        :param new_node_src_socket: The new source for the link towards dest_socket.
        :param dest_socket: The destination socket
        """
        Utility.insert_node_instead_existing_link(self.links, source_socket, new_node_dest_socket, new_node_src_socket,
                                                  dest_socket)

    def link(self, source_socket: bpy.types.NodeSocket, dest_socket: bpy.types.NodeSocket):
        """ Creates a new link between the two given sockets.

        :param source_socket: The source socket.
        :param dest_socket: The destination socket
        """
        self.links.new(source_socket, dest_socket)

    def unlink(self, source_socket: bpy.types.NodeSocket, dest_socket: bpy.types.NodeSocket):
        """ Removes the link between the two given sockets.

        :param source_socket: The source socket.
        :param dest_socket: The destination socket
        """
        links = self.links
        for link in links:
            if link.to_node == dest_socket:
                self.links.remove(link)
                break

    def map_vertex_color(self, layer_name: str = 'Col', active_shading: bool = True):
        """ Maps existing vertex color to the base color of the principled bsdf node or a new background color node.

        :param layer_name: Name of the vertex color layer. Type: string.
        :param active_shading: Whether to keep the principled bsdf shader. If True, the material properties
                               influence light reflections such as specularity, roughness, etc. alter the
                               object's appearance. Type: bool.
        """

        if active_shading:
            # create new shader node attribute
            attr_node = self.nodes.new(type='ShaderNodeAttribute')
            attr_node.attribute_name = layer_name
            # connect it to base color of principled bsdf
            principled_bsdf = self.get_the_one_node_with_type("BsdfPrincipled")
            self.links.new(attr_node.outputs['Color'], principled_bsdf.inputs['Base Color'])
        else:
            # create new vertex color shade node
            vcol = self.nodes.new(type="ShaderNodeVertexColor")
            vcol.layer_name = layer_name
            result = Utility.get_node_connected_to_the_output_and_unlink_it(self.blender_obj)
            node_connected_to_output, material_output = result
            # remove principled bsdf
            self.nodes.remove(node_connected_to_output)
            background_color_node = self.nodes.new(type="ShaderNodeBackground")
            if 'Color' in background_color_node.inputs:
                self.links.new(vcol.outputs['Color'], background_color_node.inputs['Color'])
                self.links.new(background_color_node.outputs["Background"], material_output.inputs["Surface"])
            else:
                raise RuntimeError(f"Material '{self.blender_obj.name}' has no node connected to the output, "
                                   f"which has as a 'Base Color' input.")
                    




    def remove_transparent(self):
        for node in self.get_nodes_created_in_func(self.make_transparent.__name__):
            self.remove_node(node)

        output_node = self.get_the_one_node_with_type("OutputMaterial")
        if len(self.get_nodes_with_type("BsdfPrincipled")) == 0:
            return
        
        principled_bsdf = self.get_nodes_with_type("BsdfPrincipled")[0]
        self.link(principled_bsdf.outputs['BSDF'], output_node.inputs['Surface'])

    def remove_light_indirect_effect(self):
        for node in self.get_nodes_created_in_func(self.make_light_indirect_effect.__name__):
            self.remove_node(node) 

    def remove_emissive(self):
        """ Remove emissive part of the material.
        """
        for node in self.get_nodes_created_in_func(self.make_emissive.__name__):
            self.remove_node(node)

    def remove_transparent_light(self):
        """ Remove emissive part of the material.
        """
        for node in self.get_nodes_created_in_func(self.make_transparent_light.__name__):
            self.remove_node(node)

    def remove_point_light_indirect_effect(self):
        for node in self.get_nodes_created_in_func(self.make_point_light_indirect_effect.__name__):
            self.remove_node(node)

        output_node = self.get_the_one_node_with_type("ShaderNodeOutputLight")
        emission_node = self.get_nodes_with_type("Emission")[0]
        self.link(emission_node.outputs['Emission'], output_node.inputs['Surface'])
    
    def remove_indirect_effect_v2(self):
        for node in self.get_nodes_created_in_func(self.make_indirect_effect_v2.__name__):
            self.remove_node(node) 

        output_node = self.get_the_one_node_with_type("OutputMaterial")
        if len(self.get_nodes_with_type("BsdfPrincipled")) == 0:
            return
        principled_bsdf = self.get_nodes_with_type("BsdfPrincipled")[0]
        self.link(principled_bsdf.outputs['BSDF'], output_node.inputs['Surface'])

        
    def make_transparent(self):

        self.remove_emissive()
        self.remove_transparent()

        output_node = self.get_the_one_node_with_type("OutputMaterial")
        if len(self.get_nodes_with_type("BsdfPrincipled")) == 0:
            return
        principled_bsdf = self.get_the_one_node_with_type("BsdfPrincipled")
        transparent_node = self.new_node('ShaderNodeBsdfTransparent', self.make_transparent.__name__)
        light_path_node = self.new_node('ShaderNodeLightPath', self.make_transparent.__name__)
        mix_node = self.new_node('ShaderNodeMixShader', self.make_transparent.__name__)

        self.unlink(principled_bsdf.outputs['BSDF'], output_node.inputs['Surface'])
        self.link(transparent_node.outputs['BSDF'], mix_node.inputs[1])
        self.link(principled_bsdf.outputs['BSDF'], mix_node.inputs[2])
        self.link(mix_node.outputs['Shader'], output_node.inputs['Surface'])
        self.link(light_path_node.outputs['Is Camera Ray'], mix_node.inputs['Fac'])
    
    def make_transparent_light(self, emission_strength, emission_color):
        self.remove_emissive()
        self.remove_transparent_light()

        # self.nodes = material.node_tree.nodes 
        # self.node_tree.nodes['Principled BSDF']
        output_node = self.get_the_one_node_with_type("OutputMaterial")
        principled_bsdf = self.get_the_one_node_with_type("BsdfPrincipled")

        mix_node1 = self.new_node('ShaderNodeMixShader', self.make_transparent_light.__name__)
        mix_node2 = self.new_node('ShaderNodeMixShader', self.make_transparent_light.__name__)
        Less_Than = self.new_node('ShaderNodeMath', self.make_transparent_light.__name__)
        Less_Than.operation = 'LESS_THAN'
        light_path_node = self.new_node('ShaderNodeLightPath', self.make_transparent_light.__name__)
        emission_node = self.new_node('ShaderNodeEmission', self.make_transparent_light.__name__)
        emission_node_H = self.new_node('ShaderNodeEmission', self.make_transparent_light.__name__)

        if emission_color is None:
            
            if len(principled_bsdf.inputs["Base Color"].links) == 1:
                # get the node connected to the Base Color
                socket_connected_to_the_base_color = principled_bsdf.inputs["Base Color"].links[0].from_socket
                self.link(socket_connected_to_the_base_color, emission_node.inputs["Color"])
            else:
                emission_node.inputs["Color"].default_value = principled_bsdf.inputs["Base Color"].default_value
        else:
            emission_node.inputs["Color"].default_value = emission_color
    
        emission_node.inputs['Strength'].default_value = emission_strength
        emission_node_H.inputs['Strength'].default_value = emission_strength + 1 

        self.unlink(principled_bsdf.outputs['BSDF'], output_node.inputs['Surface'])
        self.link(emission_node_H.outputs['Emission'], mix_node1.inputs[1])
        self.link(principled_bsdf.outputs['BSDF'], mix_node2.inputs[2])
        self.link(light_path_node.outputs['Transparent Depth'], Less_Than.inputs[0])
        self.link(emission_node.outputs['Emission'], mix_node1.inputs[2])
        Less_Than.inputs[1].default_value = 2.0 
        self.link(Less_Than.outputs['Value'], mix_node1.inputs['Fac'])
        self.link(light_path_node.outputs['Is Camera Ray'], mix_node2.inputs['Fac'])
        self.link(mix_node1.outputs['Shader'], mix_node2.inputs[1])
        self.link(mix_node2.outputs['Shader'],output_node.inputs['Surface'])
    
    def make_point_light_indirect_effect(self):
        self.remove_point_light_indirect_effect()
        # print(self.nodes[0].bl_idname)
        # print(self.nodes[0].bl_idname)
        output_node = self.get_the_one_node_with_type("ShaderNodeOutputLight")
        emission_node1 = self.get_nodes_with_type("Emission")[0]
        self.unlink(emission_node1.outputs['Emission'], output_node.inputs['Surface'])

        mix_node = self.new_node('ShaderNodeMixShader', self.make_point_light_indirect_effect.__name__)
        Less_Than = self.new_node('ShaderNodeMath', self.make_point_light_indirect_effect.__name__)
        Less_Than.operation = 'LESS_THAN'
        emission_node2 = self.new_node("ShaderNodeEmission", self.make_point_light_indirect_effect.__name__)
        light_path_node = self.new_node('ShaderNodeLightPath', self.make_point_light_indirect_effect.__name__)

        emission_node2.inputs['Strength'].default_value = 0.0

        self.link(light_path_node.outputs['Ray Depth'], Less_Than.inputs[0])
        self.link(emission_node1.outputs['Emission'], mix_node.inputs[1])
        self.link(emission_node2.outputs['Emission'], mix_node.inputs[2])

        Less_Than.inputs[1].default_value = 2.0
        self.link(Less_Than.outputs['Value'], mix_node.inputs['Fac'])
        self.link(mix_node.outputs['Shader'],output_node.inputs['Surface'])

    def make_light_indirect_effect(self, emission_strength: float, emission_color: List[float] = None):
        self.remove_emissive()
        self.remove_transparent()
        self.remove_light_indirect_effect()
        self.remove_transparent_light()

        # self.nodes = material.node_tree.nodes 
        # self.node_tree.nodes['Principled BSDF']
        output_node = self.get_the_one_node_with_type("OutputMaterial")
        if len(self.get_nodes_with_type("BsdfPrincipled")) == 0:
            return
        principled_bsdf = self.get_nodes_with_type("BsdfPrincipled")[0]

        mix_node1 = self.new_node('ShaderNodeMixShader', self.make_light_indirect_effect.__name__)
        mix_node2 = self.new_node('ShaderNodeMixShader', self.make_light_indirect_effect.__name__)
        Less_Than = self.new_node('ShaderNodeMath', self.make_light_indirect_effect.__name__)
        Less_Than.operation = 'LESS_THAN'
        light_path_node = self.new_node('ShaderNodeLightPath', self.make_light_indirect_effect.__name__)
        # emission_node = self.new_node('ShaderNodeEmission', self.make_light_indirect_effect.__name__)
        emission_node_bsdf = self.new_node('ShaderNodeBsdfPrincipled', self.make_emissive.__name__)
            # Subsurface IOR
        emission_node_bsdf.inputs['Subsurface'].default_value = 0.0
        emission_node_bsdf.inputs['Specular'].default_value = 0.0
        emission_node_bsdf.inputs['Roughness'].default_value = 0.0
        emission_node_bsdf.inputs['Sheen Tint'].default_value = 0.0
        emission_node_bsdf.inputs['Clearcoat Roughness'].default_value = 0.0
        emission_node_bsdf.inputs['Alpha'].default_value = 0.01

        new_bsdf = self.new_node('ShaderNodeBsdfDiffuse', self.make_light_indirect_effect.__name__)
        if emission_color is None:
            
            if len(principled_bsdf.inputs["Base Color"].links) == 1:
                # get the node connected to the Base Color
                socket_connected_to_the_base_color = principled_bsdf.inputs["Base Color"].links[0].from_socket
                # self.link(socket_connected_to_the_base_color, emission_node.inputs["Color"])
                self.link(socket_connected_to_the_base_color, emission_node_bsdf.inputs["Base Color"])
            else:
                # emission_node.inputs["Color"].default_value = principled_bsdf.inputs["Base Color"].default_value
                emission_node_bsdf.inputs["Base Color"].default_value = principled_bsdf.inputs["Base Color"].default_value
        else:
            # emission_node.inputs["Color"].default_value = emission_color
            emission_node_bsdf.inputs["Emission"].default_value = emission_color

        # set the emission strength of the shader
        # emission_node.inputs['Strength'].default_value = emission_strength
        emission_node_bsdf.inputs['Emission Strength'].default_value = emission_strength
        new_bsdf.inputs['Color'].default_value = [0.0, 0.0, 0.0 , 1.0]

        self.unlink(principled_bsdf.outputs['BSDF'], output_node.inputs['Surface'])
        self.link(new_bsdf.outputs['BSDF'], mix_node1.inputs[2])
        self.link(principled_bsdf.outputs['BSDF'], mix_node2.inputs[2])
        self.link(light_path_node.outputs['Ray Depth'], Less_Than.inputs[0])
        self.link(emission_node_bsdf.outputs['BSDF'], mix_node1.inputs[1])
        Less_Than.inputs[1].default_value = 2.0
        self.link(Less_Than.outputs['Value'], mix_node1.inputs['Fac'])
        self.link(light_path_node.outputs['Is Camera Ray'], mix_node2.inputs['Fac'])
        self.link(mix_node1.outputs['Shader'], mix_node2.inputs[1])
        self.link(mix_node2.outputs['Shader'],output_node.inputs['Surface'])

    def make_indirect_effect_v2(self, ray_length = 1.0):
        self.remove_emissive()
        self.remove_transparent()
        self.remove_transparent_light()
        self.remove_indirect_effect_v2()
        output_node = self.get_the_one_node_with_type("OutputMaterial")
        if len(self.get_nodes_with_type("BsdfPrincipled")) == 0:
            return
        principled_bsdf = self.get_nodes_with_type("BsdfPrincipled")[0]

        mix_node = self.new_node('ShaderNodeMixShader', self.make_indirect_effect_v2.__name__)
        Compare = self.new_node('ShaderNodeMath', self.make_indirect_effect_v2.__name__)
        Less_Than = self.new_node('ShaderNodeMath', self.make_indirect_effect_v2.__name__)
        Greater_Than = self.new_node('ShaderNodeMath', self.make_indirect_effect_v2.__name__)
        Modulo = self.new_node('ShaderNodeMath', self.make_indirect_effect_v2.__name__)
        Add = self.new_node('ShaderNodeMath', self.make_indirect_effect_v2.__name__)
        Multiply = self.new_node('ShaderNodeMath', self.make_indirect_effect_v2.__name__)
        # Multiply_1 = self.new_node('ShaderNodeMath', self.make_indirect_effect_v2.__name__)
        light_path_node = self.new_node('ShaderNodeLightPath', self.make_indirect_effect_v2.__name__)
        transparent_node = self.new_node('ShaderNodeBsdfTransparent', self.make_indirect_effect_v2.__name__)

        Compare.operation = 'COMPARE'
        Less_Than.operation = 'LESS_THAN'
        Greater_Than.operation = 'GREATER_THAN'
        Multiply.operation = 'MULTIPLY'
        # Multiply_1.operation = 'MULTIPLY'
        Modulo.operation = 'MODULO'
        Add.operation = 'ADD'
        Compare.inputs[1].default_value = 1.0
        Compare.inputs[2].default_value = 0.01
        Less_Than.inputs[1].default_value = ray_length
        Greater_Than.inputs[1].default_value = 0.9
        Modulo.inputs[1].default_value = 2.0

        self.unlink(principled_bsdf.outputs['BSDF'], output_node.inputs['Surface'])
        self.link(Less_Than.inputs[0], light_path_node.outputs['Ray Length'])
        self.link(Greater_Than.inputs[0], light_path_node.outputs['Ray Depth'])
        self.link(Modulo.inputs[0], light_path_node.outputs['Transparent Depth'])
        self.link(Less_Than.outputs['Value'], Multiply.inputs[0])
        self.link(Greater_Than.outputs['Value'], Multiply.inputs[1])
        self.link(Modulo.outputs['Value'], Compare.inputs[0])
        self.link(Compare.outputs['Value'], Add.inputs[0])
        self.link(Multiply.outputs['Value'], Add.inputs[1])
        self.link(Add.outputs['Value'], mix_node.inputs[0])


        

        self.link(principled_bsdf.outputs['BSDF'],  mix_node.inputs[1])
        self.link(transparent_node.outputs['BSDF'], mix_node.inputs[2])

        self.link(mix_node.outputs['Shader'],output_node.inputs['Surface'])

    def make_emissive(self, emission_strength: float, replace: bool = False, emission_color: List[float] = None,
                      non_emissive_color_socket: bpy.types.NodeSocket = None):
        """ Makes the material emit light.

        :param emission_strength: The strength of the emitted light.
        :param replace: When replace is set to True, the existing material will be completely replaced by the emission
                        shader, otherwise it still looks the same, while emitting light.
        :param emission_color: The color of the light to emit. Default: Color of the original object.
        :param non_emissive_color_socket: An output socket that defines how the material should look like. By default,
                                          that is the output of the principled shader node. Has no effect if replace
                                          is set to True.
        """
        self.remove_emissive()

        output_node = self.get_the_one_node_with_type("OutputMaterial")

        if not replace:
            mix_node = self.new_node('ShaderNodeMixShader', self.make_emissive.__name__)
            if non_emissive_color_socket is None:
                principled_bsdf = self.get_nodes_with_type("BsdfPrincipled")[0]
                non_emissive_color_socket = principled_bsdf.outputs['BSDF']
            self.insert_node_instead_existing_link(non_emissive_color_socket, mix_node.inputs[2],
                                                   mix_node.outputs['Shader'], output_node.inputs['Surface'])

            # The light path node returns 1, if the material is hit by a ray coming from the camera, else it
            # returns 0. In this way the mix shader will use the principled shader for rendering the color of
            # the emitting surface itself, while using the emission shader for lighting the scene.
            light_path_node = self.new_node('ShaderNodeLightPath', self.make_emissive.__name__)
            self.link(light_path_node.outputs['Is Camera Ray'], mix_node.inputs['Fac'])
            output_socket = mix_node.inputs[1]
        else:
            output_socket = output_node.inputs['Surface']

        # emission_node = self.new_node('ShaderNodeEmission', self.make_emissive.__name__)
        emission_node_bsdf = self.new_node('ShaderNodeBsdfPrincipled', self.make_emissive.__name__)
            # Subsurface IOR
        emission_node_bsdf.inputs['Subsurface'].default_value = 0.0
        emission_node_bsdf.inputs['Specular'].default_value = 0.0
        emission_node_bsdf.inputs['Roughness'].default_value = 0.0
        emission_node_bsdf.inputs['Sheen Tint'].default_value = 0.0
        emission_node_bsdf.inputs['Clearcoat Roughness'].default_value = 0.0
        emission_node_bsdf.inputs['Alpha'].default_value = 0.01

        if emission_color is None:
            principled_bsdf = self.get_nodes_with_type("BsdfPrincipled")[0]

            if len(principled_bsdf.inputs["Base Color"].links) == 1:
                # get the node connected to the Base Color
                socket_connected_to_the_base_color = principled_bsdf.inputs["Base Color"].links[0].from_socket
                self.link(socket_connected_to_the_base_color, emission_node_bsdf.inputs["Base Color"])
                # self.link(socket_connected_to_the_base_color, emission_node.inputs["Color"])
            else:
                # emission_node.inputs["Color"].default_value = principled_bsdf.inputs["Base Color"].default_value
                emission_node_bsdf.inputs["Base Color"].default_value = principled_bsdf.inputs["Base Color"].default_value
        else:
            emission_node_bsdf.inputs['Emission'].default_value = emission_color
            # emission_node.inputs["Color"].default_value = emission_color

        # set the emission strength of the shader
        emission_node_bsdf.inputs['Emission Strength'].default_value = emission_strength
        # emission_node.inputs['Strength'].default_value = emission_strength

        self.link(emission_node_bsdf.outputs["BSDF"], output_socket)
        # self.link(emission_node.outputs["Emission"], output_socket)

    def set_principled_shader_value(self, input_name: str, value: Union[float, bpy.types.Image, bpy.types.NodeSocket]):
        """ Sets value of an input to the principled shader node.

        :param input_name: The name of the input socket of the principled shader node.
        :param value: The value to set. Can be a simple value to use as default_value, a socket which will be
                      connected to the input or an image which will be used for a new TextureNode connected to
                      the input.
        """
        principled_bsdf = self.get_the_one_node_with_type("BsdfPrincipled")

        if isinstance(value, bpy.types.Image):
            node = self.new_node('ShaderNodeTexImage')
            node.label = input_name
            node.image = value
            self.link(node.outputs['Color'], principled_bsdf.inputs[input_name])
        elif isinstance(value, bpy.types.NodeSocket):
            self.link(value, principled_bsdf.inputs[input_name])
        else:
            if principled_bsdf.inputs[input_name].links:
                self.links.remove(principled_bsdf.inputs[input_name].links[0])
            principled_bsdf.inputs[input_name].default_value = value

    def get_principled_shader_value(self, input_name: str) -> Union[float, bpy.types.NodeSocket]:
        """
        Gets the default value or the connected node socket to an input socket of the principled shader
        node of the material.

        :param input_name: The name of the input socket of the principled shader node.
        :return: the connected socket to the input socket or the default_value of the given input_name
        """
        # get the one node from type Principled BSDF
        principled_bsdf = self.get_the_one_node_with_type("BsdfPrincipled")
        # check if the input name is a valid input
        if input_name in principled_bsdf.inputs:
            # check if there are any connections to this input socket
            if principled_bsdf.inputs[input_name].links:
                if len(principled_bsdf.inputs[input_name].links) == 1:
                    # return the connected node
                    return principled_bsdf.inputs[input_name].links[0].from_socket
                raise RuntimeError(f"The input socket has more than one input link: "
                                   f"{[link.from_node.name for link in principled_bsdf.inputs[input_name].links]}")
            # else return the default value
            return principled_bsdf.inputs[input_name].default_value
        raise RuntimeError(f"The input name could not be found in the inputs: {input_name}")

    def get_node_connected_to_the_output_and_unlink_it(self):
        """
        Searches for the OutputMaterial in the material and finds the connected node to it,
        removes the connection between this node and the output and returns this node and the material_output
        """
        material_output = self.get_the_one_node_with_type('OutputMaterial')
        # find the node, which is connected to the output
        node_connected_to_the_output = None
        for link in self.links:
            if link.to_node == material_output:
                node_connected_to_the_output = link.from_node
                # remove this link
                self.links.remove(link)
                break
        return node_connected_to_the_output, material_output

    def infuse_texture(self, texture: bpy.types.Texture, mode: str = "overlay", connection: str = "Base Color",
                       texture_scale: float = 0.05, strength: float = 0.5, invert_texture: bool = False):
        """ Overlays the selected material with a texture, this can be either a color texture like for example dirt or
        it can be a texture, which is used as an input to the Principled BSDF of the given material.

        :param texture: A texture which should be infused in the material.
        :param mode: The mode determines how the texture is used. There are three options: "overlay" in which
                     the selected texture is overlayed over a preexisting one. If there is none, nothing happens.
                     The second option: "mix" is similar to overlay, just that the textures are mixed there.
                     The last option: "set" replaces any existing texture and is even added if there was none before.
        :param connection: By default the "Base Color" input of the principled shader will be used. This can be
                           changed to any valid input of a principled shader. Default: "Base Color". For available
                           check the blender documentation.
        :param texture_scale: The used texture can be scaled down or up by a factor, to make it match the
                              preexisting UV mapping. Make sure that the object has a UV mapping beforehand.
        :param strength: The strength determines how much the newly generated texture is going to be used.
        :param invert_texture: It might be sometimes useful to invert the input texture, this can be done by
                               setting this to True.
        """
        used_mode = mode.lower()
        if used_mode not in ["overlay", "mix", "set"]:
            raise Exception(f'This mode is unknown here: {used_mode}, only ["overlay", "mix", "set"]!')

        used_connector = connection.title()

        principled_bsdf = self.get_the_one_node_with_type("BsdfPrincipled")
        if used_connector not in principled_bsdf.inputs:
            raise Exception(f"The {used_connector} is not an input to Principled BSDF!")

        node_socket_connected_to_the_connector = None
        for link in principled_bsdf.inputs[used_connector].links:
            node_socket_connected_to_the_connector = link.from_socket
            # remove this connection
            self.links.remove(link)
        if node_socket_connected_to_the_connector is not None or used_mode == "set":
            texture_node = self.new_node("ShaderNodeTexImage")
            texture_node.image = texture.image
            # add texture coords to make the scaling of the dust texture possible
            texture_coords = self.new_node("ShaderNodeTexCoord")
            mapping_node = self.new_node("ShaderNodeMapping")
            mapping_node.vector_type = "TEXTURE"
            mapping_node.inputs["Scale"].default_value = [texture_scale] * 3
            self.link(texture_coords.outputs["UV"], mapping_node.inputs["Vector"])
            self.link(mapping_node.outputs["Vector"], texture_node.inputs["Vector"])
            texture_node_output = texture_node.outputs["Color"]
            if invert_texture:
                invert_node = self.new_node("ShaderNodeInvert")
                invert_node.inputs["Fac"].default_value = 1.0
                self.link(texture_node_output, invert_node.inputs["Color"])
                texture_node_output = invert_node.outputs["Color"]
            if node_socket_connected_to_the_connector is not None and used_mode != "set":
                mix_node = self.new_node("ShaderNodeMixRGB")
                if used_mode in "mix_node":
                    mix_node.blend_type = "OVERLAY"
                elif used_mode in "mix":
                    mix_node.blend_type = "MIX"
                mix_node.inputs["Fac"].default_value = strength
                self.link(texture_node_output, mix_node.inputs["Color2"])
                # hopefully 0 is the color node!
                self.link(node_socket_connected_to_the_connector, mix_node.inputs["Color1"])
                self.link(mix_node.outputs["Color"], principled_bsdf.inputs[used_connector])
            elif used_mode == "set":
                self.link(texture_node_output, principled_bsdf.inputs[used_connector])

    def infuse_material(self, material: "Material", mode: str = "mix", mix_strength: float = 0.5):
        """
        Infuse a material inside another material. The given material, will be adapted and the used material, will
        be added, depending on the mode either as add or as mix. This change is applied to all outputs of the material,
        this includes the Surface (Color) and also the displacement and volume. For displacement mix means multiply.

        :param material: Material to infuse.
        :param mode: The mode determines how the two materials are mixed. There are two options "mix" in which the
                     preexisting material is mixed with the selected one in "used_material" or "add" in which
                     they are just added on top of each other. Available: ["mix", "add"]
        :param mix_strength: In the "mix" mode a strength can be set to determine how much of each material is
                             going to be used. A strength of 1.0 means that the new material is going to be used
                             completely.
        """
        # determine the mode
        used_mode = mode.lower()
        if used_mode not in ["add", "mix"]:
            raise Exception(f'This mode is unknown here: {used_mode}, only ["mix", "add"]!')

        # move the copied material inside of a group
        group_node = self.new_node("ShaderNodeGroup")
        group = BlenderUtility.add_nodes_to_group(material.nodes,
                                                  f"{used_mode.title()}_{material.get_name()}")
        group_node.node_tree = group
        # get the current material output and put the used material in between the last node and the material output
        material_output = self.get_the_one_node_with_type("OutputMaterial")
        for mat_output_input in material_output.inputs:
            if len(mat_output_input.links) > 0:
                if "Float" in mat_output_input.bl_idname or "Vector" in mat_output_input.bl_idname:
                    # For displacement
                    infuse_node = self.new_node("ShaderNodeMixRGB")
                    if used_mode == "mix":
                        # as there is no mix mode, we use multiply here, which is similar
                        infuse_node.blend_type = "MULTIPLY"
                        infuse_node.inputs["Fac"].default_value = mix_strength
                        input_offset = 1
                    elif used_mode == "add":
                        infuse_node.blend_type = "ADD"
                        input_offset = 0
                    else:
                        raise Exception(f"This mode is not supported here: {used_mode}!")
                    infuse_output = infuse_node.outputs["Color"]
                else:
                    # for the normal surface output (Color)
                    if used_mode == "mix":
                        infuse_node = self.new_node('ShaderNodeMixShader')
                        infuse_node.inputs[0].default_value = mix_strength
                        input_offset = 1
                    elif used_mode == "add":
                        infuse_node = self.new_node('ShaderNodeMixShader')
                        input_offset = 0
                    else:
                        raise Exception(f"This mode is not supported here: {used_mode}!")
                    infuse_output = infuse_node.outputs["Shader"]

                # link the infuse node with the correct group node and the material output
                for link in mat_output_input.links:
                    self.link(link.from_socket, infuse_node.inputs[input_offset])
                self.link(group_node.outputs[mat_output_input.name], infuse_node.inputs[input_offset + 1])
                self.link(infuse_output, mat_output_input)

    def set_displacement_from_principled_shader_value(self, input_name: str, multiply_factor: float):
        """ Connects the node that is connected to the specified input of the principled shader node
        with the displacement output of the material.

        :param input_name: The name of the input socket of the principled shader node.
        :param multiply_factor: A factor by which the displacement should be multiplied.
        """
        # Find socket that is connected with the specified input of the principled shader node.
        input_socket = self.get_principled_shader_value(input_name)
        if not isinstance(input_socket, bpy.types.NodeSocket):
            raise Exception(f"The input {input_name} of the principled shader does not have any incoming connection.")

        # Create multiplication node and connect with retrieved socket
        math_node = self.new_node('ShaderNodeMath')
        math_node.operation = "MULTIPLY"
        math_node.inputs[1].default_value = multiply_factor
        self.link(input_socket, math_node.inputs[0])

        # Connect multiplication node with displacement output
        output = self.get_the_one_node_with_type("OutputMaterial")
        self.link(math_node.outputs["Value"], output.inputs["Displacement"])

    def __setattr__(self, key, value):
        if key not in ["links", "nodes", "blender_obj"]:
            raise RuntimeError("The API class does not allow setting any attribute. Use the corresponding method or "
                               "directly access the blender attribute via entity.blender_obj.attribute_name")
        object.__setattr__(self, key, value)
