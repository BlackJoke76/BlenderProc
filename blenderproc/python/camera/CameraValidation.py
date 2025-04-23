"""Useful functions ot evaluate the objects in the camera's viewport."""

import numbers
import sys
from typing import Union, List, Set
from collections import defaultdict

import bpy
import numpy as np
from mathutils import Matrix
from mathutils.bvhtree import BVHTree
import time

from blenderproc.python.types.MeshObjectUtility import MeshObject


def perform_obstacle_in_view_check(cam2world_matrix: Union[Matrix, np.ndarray], proximity_checks: dict,
                                   bvh_tree: BVHTree, sqrt_number_of_rays: int = 64) -> bool:
    """ Check if there are obstacles in front of the camera which are too far or too close based on the given
        proximity_checks.

    :param cam2world_matrix: Transformation matrix that transforms from the camera space to the world space.
    :param proximity_checks: A dictionary containing operators (e.g. avg, min) as keys and as values dictionaries
                             containing thresholds in the form of {"min": 1.0, "max":4.0} or just the numerical
                             threshold in case of max or min. The operators are combined in conjunction
                             (i.e boolean AND). This can also be used to avoid the background in images, with the
                             no_background: True option.
    :param bvh_tree: A bvh tree containing all objects that should be considered here.
    :param sqrt_number_of_rays: The square root of the number of rays which will be used to determine the
                                visible objects.
    :return: True, if the given camera pose does not violate any of the specified proximity_checks.
    """
    if not proximity_checks:  # if no checks are in the settings all positions are accepted
        return True

    cam2world_matrix = Matrix(cam2world_matrix)

    cam_ob = bpy.context.scene.camera
    cam = cam_ob.data
    # Get position of the corners of the near plane
    frame = cam.view_frame(scene=bpy.context.scene)
    # Bring to world space
    frame = [cam2world_matrix @ v for v in frame]

    # Compute vectors along both sides of the plane
    vec_x = frame[1] - frame[0]
    vec_y = frame[3] - frame[0]

    sum_value = 0.0
    sum_sq = 0.0

    range_distance = sys.float_info.max

    # Input validation
    for operator in proximity_checks:
        if operator in ["min", "max"] and not isinstance(proximity_checks[operator], numbers.Number):
            raise RuntimeError("Threshold must be a number in perform_obstacle_in_view_check")
        if operator in ["avg", "var"]:
            if "min" not in proximity_checks[operator] or "max" not in proximity_checks[operator]:
                raise RuntimeError("Please specify the accepted interval for the avg and var operators "
                                   "in perform_obstacle_in_view_check")
            if not isinstance(proximity_checks[operator]["min"], numbers.Number) or \
                    not isinstance(proximity_checks[operator]["max"], numbers.Number):
                raise ValueError("Threshold must be a number in perform_obstacle_in_view_check")

    # If there are no average or variance operators, we can decrease the ray range distance for efficiency
    if "avg" not in proximity_checks and "var" not in proximity_checks:
        if "max" in proximity_checks:
            # Cap distance values at a value slightly higher than the max threshold
            range_distance = proximity_checks["max"] + 1.0
        else:
            range_distance = proximity_checks["min"]

    no_range_distance = False
    if "no_background" in proximity_checks and proximity_checks["no_background"]:
        # when no background is on, it can not be combined with a reduced range distance
        no_range_distance = True

    # Go in discrete grid-like steps over plane
    position = cam2world_matrix.to_translation()
    for x in range(0, sqrt_number_of_rays):
        for y in range(0, sqrt_number_of_rays):
            # Compute current point on plane
            end = frame[0] + vec_x * x / float(sqrt_number_of_rays - 1) + vec_y * y / float(sqrt_number_of_rays - 1)
            # Send ray from the camera position through the current point on the plane
            if no_range_distance:
                _, _, _, dist = bvh_tree.ray_cast(position, end - position)
            else:
                _, _, _, dist = bvh_tree.ray_cast(position, end - position, range_distance)

            # Check if something was hit and how far it is away
            if dist is not None:
                if "min" in proximity_checks and dist <= proximity_checks["min"]:
                    return False
                if "max" in proximity_checks and dist >= proximity_checks["max"]:
                    return False
                if "avg" in proximity_checks:
                    sum_value += dist
                if "var" in proximity_checks:
                    if not "avg" in proximity_checks:
                        sum_value += dist
                    sum_sq += dist * dist
            elif "no_background" in proximity_checks and proximity_checks["no_background"]:
                return False

    if "avg" in proximity_checks:
        avg = sum_value / (sqrt_number_of_rays * sqrt_number_of_rays)
        # Check that the average distance is not within the accepted interval
        if avg >= proximity_checks["avg"]["max"] or avg <= proximity_checks["avg"]["min"]:
            return False

    if "var" in proximity_checks:
        if not "avg" in proximity_checks:
            avg = sum_value / (sqrt_number_of_rays * sqrt_number_of_rays)
        sq_avg = avg * avg

        avg_sq = sum_sq / (sqrt_number_of_rays * sqrt_number_of_rays)

        var = avg_sq - sq_avg
        # Check that the variance value of the distance is not within the accepted interval
        if var >= proximity_checks["var"]["max"] or var <= proximity_checks["var"]["min"]:
            return False

    return True


def visible_objects(cam2world_matrix: Union[Matrix, np.ndarray], sqrt_number_of_rays: int = 10) -> Set[MeshObject]:
    """ Returns a set of objects visible from the given camera pose.

    Sends a grid of rays through the camera frame and returns all objects hit by at least one ray.

    :param cam2world_matrix: The world matrix which describes the camera orientation to check.
    :param sqrt_number_of_rays: The square root of the number of rays which will be used to determine the
                                visible objects.
    :return: A set of objects visible hit by the sent rays.
    """
    cam2world_matrix = Matrix(cam2world_matrix)

    visible_objects_set = set()
    cam_ob = bpy.context.scene.camera
    cam = cam_ob.data

    # Get position of the corners of the near plane
    frame = cam.view_frame(scene=bpy.context.scene)
    # Bring to world space
    frame = [cam2world_matrix @ v for v in frame]

    # Compute vectors along both sides of the plane
    vec_x = frame[1] - frame[0]
    vec_y = frame[3] - frame[0]

    # Go in discrete grid-like steps over plane
    position = cam2world_matrix.to_translation()
    for x in range(0, sqrt_number_of_rays):
        for y in range(0, sqrt_number_of_rays):
            # Compute current point on plane
            end = frame[0] + vec_x * x / float(sqrt_number_of_rays - 1) + vec_y * y / float(sqrt_number_of_rays - 1)
            # Send ray from the camera position through the current point on the plane
            _, _, _, _, hit_object, _ = bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(),
                                                                   position, end - position)
            # Add hit object to set
            if hit_object:
                visible_objects_set.add(MeshObject(hit_object))

    return visible_objects_set


def scene_coverage_score(cur_ceils, cam2world_matrix: Union[Matrix, np.ndarray], special_objects: list = None,
                         special_objects_dont_want: list = None, sqrt_number_of_rays: int = 10) -> bool:
    """ Evaluate the interestingness/coverage of the scene.

    This module tries to look at as many objects at possible, this might lead to
    a focus on the same objects from similar angles.

    Only for SUNCG and 3D Front:
        The least interesting objects: walls, ceilings, floors.

    :param cam2world_matrix: The world matrix which describes the camera pose to check.
    :param special_objects: Objects that weights differently in calculating whether the scene is interesting or not,
                            uses the coarse_grained_class or if not SUNCG, 3D Front, the category_id.
    :param special_objects_weight: Weighting factor for more special objects, used to estimate how interesting the
                                   scene is. Default: 2.0.
    :param sqrt_number_of_rays: The square root of the number of rays which will be used to determine the
                                visible objects.
    :return: the scoring of the scene.
    """
    cam2world_matrix = Matrix(cam2world_matrix)

    if special_objects is None:
        special_objects = []
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
    hit, hit_position, _, _, hit_object, _ = bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(),
                                                                    position, camera_center - position)

    distance_center_camera = ((position[0] - hit_position[0]) ** 2 + (position[1] - hit_position[1]) ** 2 + (position[2] - hit_position[2]) ** 2) ** 0.5
    
    is_this_room = False
    # for ceil in cur_ceils:
    if(cur_ceils.position_is_above_object(hit_position, [0, 0, 1], check_no_objects_in_between=False)):
        is_this_room = True
    
    if(is_this_room == False):
        return False

    if(distance_center_camera >= 5 or distance_center_camera <= 1):
        return False


    for x in range(0, sqrt_number_of_rays):
        for y in range(0, sqrt_number_of_rays):
            # Compute current point on plane
            end = frame[0] + vec_x * x / float(sqrt_number_of_rays - 1) + vec_y * y / float(sqrt_number_of_rays - 1)
            # Send ray from the camera position through the current point on the plane
            hit, _, _, _, hit_object, _ = bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(),
                                                                    position, end - position)

            if hit:
                is_of_special_dataset = "is_suncg" in hit_object or "is_3d_front" in hit_object
                is_suncg_object = "suncg_type" in hit_object and hit_object["suncg_type"] == "Object"
                is_front_3d_object = "3D_future_type" in hit_object and hit_object["3D_future_type"] == "Object"
                if is_of_special_dataset and is_suncg_object or is_of_special_dataset and is_front_3d_object:
                    # calculate the score based on the type of the object,
                    # wall, floor and ceiling objects have 0 score
                    if "coarse_grained_class" in hit_object:
                        object_class = hit_object["coarse_grained_class"]
                        objects_hit[object_class] += 1

                        # if(hit_object == cur_floor.blender_obj):
                        #     count_cur_floor += 1

                elif "category_id" in hit_object:
                    object_class = hit_object["category_id"]
                    objects_hit[object_class] += 1

                    # if(hit_object == cur_floor.blender_obj):
                    #     count_cur_floor += 1
                else:
                    objects_hit[hit_object] += 1

                    # if(hit_object == cur_floor.blender_obj):
                    #     count_cur_floor += 1



    total = num_of_rays
    count_category = 0
    count_dont_want = 0
    count_no_bg = 0

    for ele in objects_hit.values():
        count_no_bg += ele

    if count_no_bg / total < 0.99:
        print("bg")
        return False

    special_objects_dont_want=list(set(special_objects_dont_want))
    for ele in special_objects_dont_want:
        count_dont_want += objects_hit[ele]

    if(count_dont_want != 0):
        print("dont want")
        return False


    # count_floor = objects_hit[19]
    # count_floor += objects_hit[29]
    # if(count_cur_floor / (count_floor + 1) < 0.7):
    #     return False

    count_want = 0
    special_objects=list(set(special_objects))
    for ele in special_objects:
        if(objects_hit[ele] / total > 0.25):
            print("big want")
            return False

        if(objects_hit[ele] / total > 0.05):
            count_category += 1

        count_want += objects_hit[ele]

    if(count_want / total < 0.15):
        print("small want")
        return False
    
    count_wall = objects_hit[26]
    count_wall += objects_hit[45]
    count_wall += objects_hit[80]
    count_wall += objects_hit[103]
    count_wall += objects_hit[147]
    count_wall += objects_hit[185]
    count_wall += objects_hit[200]
    count_wall += objects_hit[92]
    count_wall += objects_hit[89]
    count_wall += objects_hit[101]
    # count_wall += np.sum(seg_image == 168)

    count_floor = objects_hit[19]
    count_floor += objects_hit[29]

    percent_floor = count_floor / total
    percent_wall = count_wall / total
    precent_tatol = percent_floor + percent_wall + objects_hit[168] / total

    
    if(precent_tatol > 0.2 and precent_tatol < 0.65 and percent_floor > 0.1 and count_category >= 2):
        return True
    else:
        print("wall")
        return False


def decrease_interest_score(interest_score: float, min_interest_score: float, interest_score_step: float):
    """ Decreases the interest scores in the given interval

    :param interest_score: The current interest score.
    :param min_interest_score: The minimum desired interest scores.
    :param interest_score_step: The step size in which the interest score should be reduced.
    :return: Returns the new interest score, and True/False if minimum has not been reached.
    """
    if interest_score <= min_interest_score:
        return False, interest_score
    return True, interest_score - interest_score_step


def check_novel_pose(cam2world_matrix: Union[Matrix, np.ndarray], existing_poses: List[Union[Matrix, np.ndarray]],
                     check_pose_novelty_rot: bool, check_pose_novelty_translation: bool,
                     min_var_diff_rot: float = -1, min_var_diff_translation: float = -1):
    """ Checks if a newly sampled pose is novel based on variance checks.

    :param cam2world_matrix: The world matrix which describes the camera pose to check.
    :param existing_poses: The list of already sampled valid poses.
    :param check_pose_novelty_rot: Checks that a sampled new pose is novel with respect to the rotation component.
    :param check_pose_novelty_translation: Checks that a sampled new pose is novel with respect to the
                                           translation component.
    :param min_var_diff_rot: Considers a pose novel if it increases the variance of the rotation component of all
                             poses sampled by this parameter's value in percentage. If set to -1, then it would only
                             check that the variance is increased. Default: sys.float_info.min.
    :param min_var_diff_translation: Same as min_var_diff_rot but for translation. If set to -1, then it would only
                                     check that the variance is increased. Default: sys.float_info.min.
    :return: True, if the given pose is novel.
    """
    def _variance_constraint(array, new_val, old_var, diff_threshold, mode):
        array.append(new_val)
        var = np.var(array)

        if var < old_var:
            array.pop()
            return False

        diff = ((var - old_var) / old_var) * 100.0
        print(f"Variance difference {mode}: {diff}")
        if diff < diff_threshold:  # Check if the variance increased sufficiently
            array.pop()
            return False

        return True

    if len(existing_poses) > 0:  # First pose is always novel
        cam2world_matrix = Matrix(cam2world_matrix)
        if check_pose_novelty_rot:
            rotations = [Matrix(pose).to_euler() for pose in existing_poses]
            var_rot = np.var(rotations)

            if not _variance_constraint(rotations, cam2world_matrix.to_euler(), var_rot, min_var_diff_rot, "rotation"):
                return False

        if check_pose_novelty_translation:
            translations = [Matrix(pose).to_translation() for pose in existing_poses]
            var_translation = np.var(translations)

            if not _variance_constraint(translations, cam2world_matrix.to_translation(), var_translation,
                                        min_var_diff_translation, "translation"):
                return False

    return True
