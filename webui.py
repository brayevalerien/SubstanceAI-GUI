import os
import gradio as gr
from api_manager import AVAILABLE_RESOLUTIONS, compose_2D_3D, upload_to_space
from random import randint

VERSION = "0.2.0 (beta)"
TITLE = f"SubstanceAI GUI v{VERSION}"

def call_api(api_key, scene_file: str, prompt: str, hero: str, camera: str, image_count: int, seed: int, resolution: str) -> tuple:
    """
    Runs a generation job after checking input sanity.

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
    if api_key is None:
        raise gr.Error("Missing API key, please log in at https://s3d.adobe.io/ to get yours.", title="Input Error")
    if scene_file is None:
        raise gr.Error("Missing scene file, please load a GLB file.", title="Input Error")
    if not scene_file.split(".")[-1].lower() in ["glb", "fbx", "usdz"]:
        raise gr.Error("Invalid scene file format, please load a GLB file.", title="Input Error")
    if hero is None:
        raise gr.Error("Missing hero object, please add the exact name of the hero object in the 3D scene.", title="Input Error")
    if camera is None:
        raise gr.Error("Missing camera, please add the exact name of the camera in the 3D scene.", title="Input Error")
    if image_count is None:
        raise gr.Error("Missing image count.", title="Input Error")
    if seed is None:
        raise gr.Error("Missing seed.", title="Input Error")
    elif seed == -1:
        seed = randint(0, 2**31-1) # limiting seed range to positive int32 but that should be enough...
    if not resolution:
        raise gr.Error("Missing resolution.", title="Input Error")
    if prompt is None or len(prompt) == 0:
        raise gr.Error("Missing prompt.", title="Input Error")
    return compose_2D_3D(api_key, scene_file, prompt, hero, camera, image_count, seed, resolution)

with gr.Blocks(title=TITLE, analytics_enabled=False, theme='Zarkel/IBM_Carbon_Theme') as demo:
    with gr.Row():
        with gr.Column(scale=2):
            result = gr.Gallery(label="Result", format="png", type="filepath", interactive=False)
            with gr.Group() as input_group:
                scene_file_input = gr.File(label="Upload 3D scene file in GLB format")
                with gr.Row():
                    with gr.Column(scale=2):
                        prompt_input = gr.TextArea(label="Prompt", placeholder="Write what you want to see in the image here.")
                    with gr.Column(scale=1):
                        hero_input = gr.Textbox(
                            label="Hero object",
                            info="Exact name of the product in the scene file",
                            interactive=True
                        )
                        camera_input = gr.Textbox(
                            label="Camera",
                            info="Exact name of the camera in the scene file", value="Camera", interactive=True
                        )
                with gr.Row():
                    generate = gr.Button(value="Generate", variant="primary")
        
        with gr.Column(variant="panel") as settings_column:
            gr.Markdown("# Settings")
            with gr.Group():
                api_key_input = gr.Textbox(
                    label="API key",
                    info="Get your API key by logging in at https://s3d.adobe.io/",
                    max_lines=1,
                )
            with gr.Group():
                image_count_input = gr.Slider(
                    label="Image count",
                    minimum=1, maximum=4,
                    step=1, interactive=True
                )
                seed_input = gr.Number(
                    label="Seed", info="Set to -1 for random seed", minimum=-1
                )    
            with gr.Group():
                resolution_input = gr.Radio(
                    label="Resolution", choices=AVAILABLE_RESOLUTIONS.keys(),
                    value=list(AVAILABLE_RESOLUTIONS.keys())[0], interactive=True
                )
            with gr.Group():
                gr.Markdown("Please note that the style image is an upcoming feature and is **not implemented yet**. Uploading an image here will have no effect.")
                gr.Image(label="Style image")
    with gr.Accordion(label="Data exchange (dev view)", open=False) as dev_view:
        with gr.Row():
            request_display = gr.JSON(label="Request", max_height=None)
            response_display = gr.JSON(label="Response", max_height=None)
              
    # generate.click(
    #     fn=upload_to_space,
    #     inputs=[api_key_input, scene_file_input]
    # )
    generate.click(
        fn = call_api,
        inputs=[
            api_key_input,
            scene_file_input, prompt_input,
            hero_input, camera_input,
            image_count_input, seed_input,
            resolution_input
        ],
        outputs=[result, request_display, response_display]
    )

if __name__ == "__main__":
    demo.launch(inbrowser=True)