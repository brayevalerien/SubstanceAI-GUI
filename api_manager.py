import json
import requests
import os
import gradio as gr
from datetime import datetime
from time import sleep

API_URL = "https://s3d.adobe.io"
API_SPACE_ENDPOINT = f"{API_URL}/v1beta/spaces"
API_COMPOSE_ENDPOINT = f"{API_URL}/v1beta/3dscenes/compose"
API_JOB_ENDPOINT = f"{API_URL}/v1beta/jobs/"

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

def handle_error(error_code: int):
    """
    Raises an error depending on the HTTP error code. The error is a gradio.Error that will show up in the UI.

    Args:
        error_code (int): _description_

    Raises:
        gr.Error: _description_
    """
    # TODO: error handling should be moved to webui.py to avoid writting gradio code here.
    error_messages = {
        400: "Bad request",
        403: "Access forbidden",
        408: "Request timeout",
        413: "Request entity too large",
        415: "Unsopported media type",
        422: "Unprocessable entity",
        429: "Too many requests",
        500: "Internal server error",
    }
    try:
        message = error_messages[error_code]
    except KeyError:
        message = "Unknown error"
    finally:
        print(f"[Error {error_code}] {message}") # debug
        raise gr.Error(message, title=f"Error {error_code}")

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
    print("Asking for space creation...") # debug
    response = requests.post(API_SPACE_ENDPOINT, data=payload, files=files, headers=headers)
    
    if response.status_code == 201:
        print("Space created successfully.") # debug
        return response.json()["id"]
    else:
        handle_error(response.status_code)

def post_request(api_key: str, space_id: str, prompt: str, hero: str, camera: str, image_count: int, seed: int, resolution: str) -> tuple:
    """
    Given the various inputs, posts an API request and wait for the job to be finished. It returns the API response only if the job is finished successfully. The payload sent to the API is returned too.

    Args:
        api_key (str)
        space_id (str): space ID where the scene file is stored
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
        "prompt": prompt,
        "seeds": [seed+i for i in range(image_count)],
        "size": AVAILABLE_RESOLUTIONS[resolution],
        "sources": [{
            "space": {"id": space_id}
        }]
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer " + api_key
    }
    print("Requesting 2D/3D composition job...") # debug
    response = requests.post(API_COMPOSE_ENDPOINT, json=payload, headers=headers)
    
    if response.status_code == 202:
        job_id = response.json()["id"]
        print(f"2D/3D composition job {job_id} started successfully...") # debug
    else:
        handle_error(response.status_code)

    retry_after = response.headers["Retry-After"]
    while True:
        job_response = requests.get(f"{API_JOB_ENDPOINT}/{job_id}", headers=headers)
        status = job_response.json()["status"]
        if status in ["not_started", "running"]:
            print(f"Job status: {status} (fetching status again in {retry_after}s.)") # debug
        elif status == "succeeded":
            return payload, job_response.json()
        elif status == "failed":
            api_error_message = job_response.json()["error"]
            print(f"[Error] {api_error_message}") # debug
            gr.Error(f"2D/3D composition job failed: {api_error_message}")
            return payload, job_response.json()
        sleep(int(retry_after)) # use callback instead when API implements it to stay asynchronous

def save_image(image_data, output_directory: str="./output/") -> str:
    """
    Given raw image bytes, saves them to a new png file inside the specified output directory.

    Args:
        image_data: image bytes
        output_directory (str): directory where the image should be saved.

    Returns:
        str: path to the saved image.
    """
    output_directory = os.path.join(output_directory, datetime.today().strftime('%Y-%m-%d'))
    os.makedirs(output_directory, exist_ok=True)
    img_num = 1
    filename = f"substanceai_{img_num:05d}.png"
    filepath = os.path.join(output_directory, filename)
    while os.path.exists(filepath):
        img_num +=1
        if img_num >= 100000:
            raise gr.Error(f"Cannot save the image because the output directory ({output_directory}) is full.", title="Save Error")
        filename = f"substanceai_{img_num:05d}.png"
        filepath = os.path.join(output_directory, filename)
    with open(filepath, "wb") as f:
        f.write(image_data)
        print(f"Saved image at {filepath}")
    return filepath

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
            list: a list of str, the paths to the resulting images (that will be saved to the disk)
            dict: request json
            dict: response json
    """
    print(f"\n{' Starting generation ':=^50}")
    space_id = upload_to_space(api_key, scene_file)
    request, response = post_request(api_key, space_id, prompt, hero, camera, image_count, seed, resolution)
    try:
        image_paths = []
        for output in response["result"]["outputs"]:
            image_url = output["image"]["url"] # raw image bytes
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": "Bearer " + api_key
            }
            image_data = requests.get(image_url, headers=headers).content
            image_paths.append(save_image(image_data, f"./output/"))
    except KeyError:
        image_paths = ["./assets/error.png"]
    print(f"{'':=^50}\n")
    return image_paths, request, response