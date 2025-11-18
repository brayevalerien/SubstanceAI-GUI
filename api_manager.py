import os
from datetime import datetime
from time import sleep

import gradio as gr
import requests

import utils

API_URL = "https://s3d.adobe.io"
API_SPACE_ENDPOINT = f"{API_URL}/v1/spaces"
API_COMPOSE_ENDPOINT = f"{API_URL}/v1/composites/compose"
API_JOB_ENDPOINT = f"{API_URL}/v1/jobs/"

# Valid resolutions for the Substance API, see:
# https://s3d.adobe.io/docs#/operations/v1/composites/compose#request-body
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
AVAILABLE_RESOLUTIONS_IMAGE4 = {
    "2048 × 2048 | 1:1": {"width": 2048, "height": 2048},
    "2304 × 1792 | 4:3": {"width": 2304, "height": 1792},
    "1792 × 2304 | 3:4": {"width": 1792, "height": 2304},
    "2688 × 1536 | 16:9": {"width": 2688, "height": 1536},
}
AVAILABLE_CONTENTCLASSES = ["photo", "art"]
AVAILABLE_MODELS = {
    "Firefly Image 3": "image3_fast",
    "Firefly Image 4": "image4_standard",
    "Firefly Image 4 Ultra": "image4_ultra",
}


def get_bearer_token(client_id: str, client_secret: str) -> str:
    """
    Generates a new Bearer token from client credentials using the Adobe login API.

    Args:
        client_id (str)
        client_secret (str)

    Raises:
        gr.Error: invalid client credentials

    Returns:
        str: the generated Bearer token
    """
    assert client_id and client_secret, "Cannot authentificate if the client ID or secret is None"
    url = "https://ims-na1.adobelogin.com/ims/token/v3"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "openid, AdobeID, firefly_api, ff_apis, read_organizations, substance3d_api.jobs.create, email, profile, substance3d_api.spaces.create",
    }
    headers = {"content-type": "application/x-www-form-urlencoded"}
    response = requests.post(url, data=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["access_token"]
    raise gr.Error(
        f"Could not authentificate: {response.json()['error']}\nPlease update CLIENT_ID and CLIENT_SECRET env variables and restart the app.",
        title=f"Error {response.status_code}",
    )


class SpaceDesc:
    """
    A class describing a space.
    """

    def __init__(self, name: str, id: str, creation_time: datetime, lifetime: int = 6):
        self.name = name
        self.id = id
        self.creation_time = creation_time
        self.lifetime = lifetime  # lifetime of a space in the API

    def is_alive(self) -> bool:
        delta = datetime.now() - self.creation_time
        hours = delta.days // 24 + delta.seconds // 3600
        return hours < self.lifetime


class SpaceCache:
    """
    A caching structure for Substance API spaces, allowing to store file hashes and the associated spaces, and remove spaces that are dead (older than their lifetime).
    """

    def __init__(self):
        # a dict where values are file hashes and values are the associated spaces.
        self.data = {}

    def get(self, hash: str) -> SpaceDesc:
        if hash not in self.data:
            raise KeyError(f"No space associated with hash {hash} stored in this SpaceCache.")
        return self.data[hash]

    def add(self, hash: str, space_desc: SpaceDesc) -> bool:
        """
        Adds a new element to the cache if it isn't stored yet. If the element already exists but the associated space is dead (lifetime is over), updates the space descriptor.

        Args:
            hash (str): hash of the file stored in the space.
            space_desc (SpaceDesc): description of the space.

        Returns:
            bool: True if the element was added (not already in the cache) OR if it was updated (already in the cache but space was dead), False if the element was already stored.
        """
        if hash in self.data:
            if self.data[hash].is_alive():
                return False
        self.data[hash] = space_desc

    def exists(self, hash: str) -> bool:
        """
        Checks if a space with a given hash already exists in the cache.
        """
        self.purge()
        return hash in self.data

    def purge(self):
        """
        Removes all dead spaces from the cache (spaces that have been opened for longer than their lifetime).
        """
        for k, v in self.data.items():
            if not v.is_alive():
                # shallow copy is ok since we remove the reference (hash) to the item. The SpaceDesc will be removed by the garbage collector.
                data_copy = self.data.copy()
                del data_copy[k]
                self.data = data_copy


class APIHandler:
    def __init__(self):
        # Note: we don't store the API credentials here since it currently dies after 86399 seconds. API credentials needs to be passed to the functions of the API handler instead.
        # If client credentials are given, we can store them in the browser, that is not implemented yet.
        self.space_cache = SpaceCache()

    def handle_error(self, error_code: int):
        """
        Raises an error depending on the HTTP error code. The error is a gradio.Error that will show up in the UI.

        Args:
            error_code (int)

        Raises:
            gr.Error
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
            print(f"[Error {error_code}] {message}")  # debug
            raise gr.Error(message, title=f"Error {error_code}")

    def upload_to_space(self, api_key: str, scene_filepath: str, style_image_filepath: str = None) -> str:
        """
        Uploads content to Substance API space.
        Learn more at https://s3d.adobe.io/v1beta/docs#/paths/v1beta-spaces/post

        Args:
            api_key (str)
            scene_filepath (str): path to the local 3D scene file to be uploaded to the Substance API.
            scene_filepath (str): path to the local style image to be uploaded to the Substance API. Defaults to None.

        Returns:
            str: ID of the space where the files has been uploaded.
        """
        file_hash = utils.hash_files([scene_filepath, style_image_filepath])
        if self.space_cache.exists(file_hash):
            print("Using an already existing space for this file.")
            return self.space_cache.get(file_hash).id

        filename = os.path.basename(scene_filepath)
        files = {"3d_scene": open(scene_filepath, "rb")}
        if style_image_filepath is not None:
            files["style_image"] = open(style_image_filepath, "rb")
        headers = {"Accept": "application/json", "Authorization": "Bearer " + api_key}
        print("Asking for space creation...")  # debug
        response = requests.post(API_SPACE_ENDPOINT, files=files, headers=headers)

        if response.status_code == 201:
            print(f"Space created successfully at {response.json()['url']}.")  # debug
            space_id = response.json()["id"]
            # add space to cache
            self.space_cache.add(
                file_hash,
                SpaceDesc(filename, space_id, datetime.now()),
            )
            return space_id
        else:
            self.handle_error(response.status_code)

    def post_request(
        self,
        api_key: str,
        space_id: str,
        prompt: str,
        hero: str,
        camera: str,
        image_count: int,
        seed: int,
        resolution: str,
        content_class: str,
        style_image_name: str,
        style_image_strenght: int,
        model_id: str,
        lighting_seed: int,
        enable_groundplane: bool,
    ) -> tuple:
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
            content_class (str): can be "photo" or "art".
            style_image_name (str): name of the style image in the space (e.g. "style_image/mystyle.png"). Ignored if None.
            style_image_strength (int): strength of the style reference image over the generation. Ignored if style_image_name is None.
            model_id (str): id of the image generation model.
            lighting_seed (int):
            enable_groundplane (bool): enable the auto generated groundplane under the hero asset.

        Returns:
            tuple: a couple of two dicts:
                dict: the payload of the request sent to the API
                dict: the API response
        """
        payload = {
            "cameraName": camera,
            "heroAsset": hero,
            "prompt": prompt,
            "seeds": [seed + i for i in range(image_count)],
            "size": AVAILABLE_RESOLUTIONS[resolution],
            "sources": [{"space": {"id": space_id}}],
            "contentClass": content_class,
            "modelVersion": model_id,
            "enableGroundPlane": True,
            "lightingSeeds": [lighting_seed + i for i in range(image_count)],
            "enableGroundPlane": enable_groundplane,
        }
        if style_image_name is not None:
            payload["styleImage"] = style_image_name
            payload["styleImageStrength"] = style_image_strenght
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer " + api_key,
        }
        print("Requesting 2D/3D composition job...")  # debug
        response = requests.post(API_COMPOSE_ENDPOINT, json=payload, headers=headers)

        if response.status_code == 202:
            job_id = response.json()["id"]
            print(f"2D/3D composition job {job_id} started successfully...")  # debug
        else:
            self.handle_error(response.status_code)

        retry_after = response.headers["Retry-After"]
        while True:
            job_response = requests.get(f"{API_JOB_ENDPOINT}/{job_id}", headers=headers)
            status = job_response.json()["status"]
            if status in ["not_started", "running"]:
                print(f"Job status: {status} (fetching status again in {retry_after}s.)")  # debug
            elif status == "succeeded":
                return payload, job_response.json()
            elif status == "failed":
                api_error_message = job_response.json()["error"]
                print(f"[Error] {api_error_message}")  # debug
                gr.Error(f"2D/3D composition job failed: {api_error_message}")
                return payload, job_response.json()
            sleep(int(retry_after))  # use callback instead when API implements it to stay asynchronous

    def compose_2D_3D(
        self,
        api_key: str,
        scene_file: str,
        prompt: str,
        hero: str,
        camera: str,
        image_count: int,
        seed: int,
        resolution: str,
        content_class: str,
        style_image: str,
        style_image_strength: int,
        model_name: str,
        lighting_seed: int,
        enable_groundplane: bool,
    ) -> tuple:
        """
        Calls the Substance API compose 2D and 3D endpoint, with proper file and input management.

        Args:
            api_key (str)
            scene_file (str): 3D scene file, expects a GLB or USDz file (.glb or .usdz format, exported from Blender for instance)
            prompt (str): textual prompt describing what has to be seen in the result.
            hero (str): name of the hero object in the scene file (this object will be left untouched by the AI).
            camera (str): name of a camera in the scene file.
            image_count (int): number of variations to generate.
            seed (int): initial seed, will be incremented for each variation.
            resolution (str): render resolution, must be a key of AVAILABLE_RESOLUTIONS.
            content_class (str): can be "photo" or "art".
            style_image (str): path to the image file for style reference. Ignored if None.
            style_image_strength (int): strength of the style reference image over the generation. Ignored if style_image is None.
            model_name (str): name of the image generation model.
            lighting_seed (int): initial seed, will be incremented for each variation.
            enable_groundplane (bool): enable the auto generated groundplane under the hero asset.

        Returns:
            tuple: a tuple of 3 elements:
                list: a list of str, the paths to the resulting images (that will be saved to the disk)
                dict: request json
                dict: response json
        """
        print(f"\n{' Starting generation ':=^50}")
        space_id = self.upload_to_space(api_key, scene_file, style_image)
        style_image_name = f"style_image/{os.path.basename(style_image)}" if style_image is not None else None
        model_id = AVAILABLE_MODELS[model_name]
        request, response = self.post_request(
            api_key,
            space_id,
            prompt,
            hero,
            camera,
            image_count,
            seed,
            resolution,
            content_class,
            style_image_name,
            style_image_strength,
            model_id,
            lighting_seed,
            enable_groundplane,
        )
        try:
            image_paths = []
            for output in response["result"]["outputs"]:
                image_url = output["image"]["url"]  # raw image bytes
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    # "Authorization": "Bearer " + api_key,
                }
                image_data = requests.get(image_url, headers=headers).content
                image_paths.append(utils.save_image(image_data, "./output/"))
        except KeyError:
            image_paths = ["./assets/error.png"]
        print(f"{'':=^50}\n")
        return image_paths, request, response
