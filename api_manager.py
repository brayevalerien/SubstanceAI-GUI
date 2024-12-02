import json
import requests
import os
import gradio as gr
from datetime import datetime

API_SPACE_ENDPOINT = "https://s3d.adobe.io/v1beta/spaces"
API_COMPOSE_ENDPOINT = "https://s3d.adobe.io/v1beta/3dscenes/compose"

# Valid resolutions for the Substance API, see:
# https://s3d.adobe.io/v1beta/docs#/paths/v1beta-3dscenes-compose/post#request-body
AVAILABLE_RESOLUTIONS = {
    "2048 × 2048 | 1:1": {"width": 2048, "height": 2048},
    "2304 × 1792 | 4:3": {"width": 2304, "height": 1792},
    "1792 × 2304 | 3:4": {"width": 1792, "height": 2304},
    "2688 × 1536 | 16:9": {"width": 2688, "height": 1536},
    "1344 × 768  | 7:4": {"width": 1344, "height": 768},
    "1152 × 896  | 9:7": {"width": 1152, "height": 896},
    "896  × 1152 | 7:9": {"width": 896, "height": 1152},
    "1024 × 1024 | 1:1": {"width": 1024, "height": 1024},
}

def upload_to_space(api_key: str, file_path: str) -> str:
    """
    Uploads content to Substance API space.
    Learn more at https://s3d.adobe.io/v1beta/docs#/paths/v1beta-spaces/post

    Args:
        api_key (str)
        file_path (str): path to the local file to be uploaded to the Substance API.

    Returns:
        str: ID of the space where the file has been uploaded.
    """
    filename = os.path.basename(file_path)
    files = {"filename": open(file_path, 'rb')}
    payload = {"name": filename}
    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer " + api_key
    }
    print("\n\n========= UPLOADING FILE TO SPACE =========\n\n") # debug
    response = requests.post(API_SPACE_ENDPOINT, data=payload, files=files, headers=headers)
    print(f"{response = }\n") # debug
    if response.status_code == 200:
        return response.json()["id"]
    else:
        # TODO: error handling should be moved to webui.py to avoid writting gradio code here.
        error_code = response.status_code
        try:
            message = response.json()["message"]
        except:
            if error_code == 403:
                message = "Access to this ressource is forbidden."
            else:
                message = "No additional information message."
        print(f"[Error {error_code}] {message}") # debug
        raise gr.Error(message, title=f"Error {error_code}")

def post_request(api_key: str, scene_file_space: str, prompt: str, hero: str, camera: str, image_count: int, seed: int, resolution: str) -> tuple:
    """
    Given the various inputs, posts an API request and wait for the job to be finished. It returns the API response only if the job is finished successfully. The payload sent to the API is returned too.

    Args:
        api_key (str)
        scene_file_space (str): space ID where the scene file is stored
        prompt (str): textual prompt describing what has to be seen in the result.
        hero (str): name of the hero object in the scene file (this object will be left untouched by the AI).
        camera (str): name of a camera in the scene file.
        image_count (int): number of variations to generate.
        seed (int): initial seed, will be incremented for each variation.
        resolution (str): render resolution, must be a key of AVAILABLE_RESOLUTIONS.

    Returns:
        tuple: a couple of two dicts:
            dict: the payload of the request sent to the API
            dict: the API response
    """
    payload = {
        "cameraName": camera,
        "heroAsset": hero,
        "numVariations": image_count, # added for clarity but could be removed
        "prompt": prompt,
        "seeds": [seed+i for i in range(image_count)],
        "size": AVAILABLE_RESOLUTIONS[resolution],
        "sources": [{
            "space": {"id": scene_file_space}
        }]
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer " + api_key
    }
    response = requests.post(API_COMPOSE_ENDPOINT, json=payload, headers=headers)
    # TODO write the loop to wait for the job to finish and check success
    return payload, response.json()

def save_image(image_data, output_directory: str="./output/") -> str:
    """
    Given raw image bytes, saves them to a new png file inside the specified output directory.

    Args:
        image_data: image bytes
        output_directory (str): directory where the image should be saved.

    Returns:
        str: path to the saved image.
    """
    filename = "substanceai.png" # TODO find next available name
    # TODO actually write image to disk
    return os.path.join(output_directory, filename)

def compose_2D_3D(api_key: str, scene_file: str, prompt: str, hero: str, camera: str, image_count: int, seed: int, resolution: str) -> tuple:
    """
    Calls the Substance API compose 2D and 3D endpoint, with proper file and input management.

    Args:
        api_key (str)
        scene_file (str): 3D scene file, expects a GLB file (.glb format, exported from Blender for instance)
        prompt (str): textual prompt describing what has to be seen in the result.
        hero (str): name of the hero object in the scene file (this object will be left untouched by the AI).
        camera (str): name of a camera in the scene file.
        image_count (int): number of variations to generate.
        seed (int): initial seed, will be incremented for each variation.
        resolution (str): render resolution, must be a key of AVAILABLE_RESOLUTIONS.

    Returns:
        tuple: a tuple of 3 elements:
            str: path to the resulting image (that will be saved to the disk)
            dict: request json
            dict: response json
    """
    # TODO add input sanity check
    scene_file_space = upload_to_space(api_key, scene_file)
    request, response = post_request(api_key, scene_file_space, prompt, hero, camera, image_count, seed, resolution)
    image_data = response["result"]["outputs"][0]["image"] # raw image bytes
    image_path = save_image(image_data, f"./output/{datetime.today().strftime('%Y-%m-%d')}")
    return image_path, request, response