import os
from random import randint

import gradio as gr

from api_manager import AVAILABLE_RESOLUTIONS, AVAILABLE_CONTENTCLASSES, APIHandler

VERSION = "0.4.0 (beta)"
TITLE = f"SubstanceAI GUI v{VERSION}"


def call_api(
    api_handler: APIHandler,
    api_key,
    scene_file: str,
    prompt: str,
    hero: str,
    camera: str,
    image_count: int,
    seed: int,
    resolution: str,
    content_class: str,
    style_image: str,
) -> tuple:
    """
    Runs a generation job after checking input sanity.

    Args:
        api_handler (APIHandler)
        api_key (str)
        scene_file (str): 3D scene file, expects a GLB file (.glb format, exported from Blender for instance)
        prompt (str): textual prompt describing what has to be seen in the result.
        hero (str): name of the hero object in the scene file (this object will be left untouched by the AI).
        camera (str): name of a camera in the scene file.
        image_count (int): number of variations to generate.
        seed (int): initial seed, will be incremented for each variation.
        resolution (str): render resolution, must be a key of AVAILABLE_RESOLUTIONS.
        content_class (str): can be "photo" or "art".
        style_image (str): path to the image file for style reference. Ignored if None.

    Returns:
        tuple: a tuple of 3 elements:
            list: a list of str, the paths to the resulting images (that will be saved to the disk)
            dict: request json
            dict: response json
    """
    if api_key is None:
        raise gr.Error(
            "Missing API key, please log in at https://s3d.adobe.io/ to get yours.",
            title="Input Error",
        )
    if scene_file is None:
        raise gr.Error(
            "Missing scene file, please load a GLB file.", title="Input Error"
        )
    if not scene_file.split(".")[-1].lower() in ["glb", "fbx", "usdz"]:
        raise gr.Error(
            "Invalid scene file format, please load a GLB file.", title="Input Error"
        )
    if hero is None:
        raise gr.Error(
            "Missing hero object, please add the exact name of the hero object in the 3D scene.",
            title="Input Error",
        )
    if camera is None:
        raise gr.Error(
            "Missing camera, please add the exact name of the camera in the 3D scene.",
            title="Input Error",
        )
    if image_count is None:
        raise gr.Error("Missing image count.", title="Input Error")
    if seed is None:
        raise gr.Error("Missing seed.", title="Input Error")
    elif seed == -1:
        seed = randint(
            0, 2**31 - 1
        )  # limiting seed range to positive int32 but that should be enough...
    if not resolution:
        raise gr.Error("Missing resolution.", title="Input Error")
    if prompt is None or len(prompt) == 0:
        raise gr.Error("Missing prompt.", title="Input Error")
    content_class = content_class.lower()
    if not content_class in AVAILABLE_CONTENTCLASSES:
        gr.Warning(
            f'Content class must be of [{", ".join(AVAILABLE_CONTENTCLASSES)}] (got {content_class}). Defaulting to "photo".'
        )
        content_class = "photo"
    if (not style_image is None) and (not os.path.isfile(style_image)):
        raise gr.Error(
            "A style image has been provided but is invalid. Please check that the image still exists and that it can be read.",
            title="Input Error",
        )
    return api_handler.compose_2D_3D(
        api_key,
        scene_file,
        prompt,
        hero,
        camera,
        image_count,
        seed,
        resolution,
        content_class,
        style_image,
    )


css = """
.resizable_vertical {
  resize: vertical;
  overflow: auto !important;
}
"""

with gr.Blocks(
    title=TITLE, analytics_enabled=False, theme="Zarkel/IBM_Carbon_Theme", css=css
) as demo:
    api_handler = gr.State(APIHandler())
    with gr.Row():
        with gr.Column(scale=2):
            result = gr.Gallery(
                label="Result",
                format="png",
                type="filepath",
                object_fit="contain",
                interactive=False,
                height=512,
                elem_classes=["resizable_vertical"],
            )
            with gr.Group() as input_group:
                scene_file_input = gr.File(label="Upload 3D scene file in GLB format")
                with gr.Row():
                    with gr.Column(scale=2):
                        prompt_input = gr.TextArea(
                            label="Prompt",
                            placeholder="Write what you want to see in the image here.",
                        )
                    with gr.Column(scale=1):
                        hero_input = gr.Textbox(
                            label="Hero object",
                            info="Exact name of the product in the scene file",
                            interactive=True,
                        )
                        camera_input = gr.Textbox(
                            label="Camera",
                            info="Exact name of the camera in the scene file",
                            value="Camera",
                            interactive=True,
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
                    type="password",
                )
            with gr.Group():
                image_count_input = gr.Slider(
                    label="Image count", minimum=1, maximum=4, step=1, interactive=True
                )
                seed_input = gr.Number(
                    label="Seed", info="Set to -1 for random seed", minimum=-1
                )
            with gr.Group():
                resolution_input = gr.Radio(
                    label="Resolution",
                    choices=AVAILABLE_RESOLUTIONS.keys(),
                    value=list(AVAILABLE_RESOLUTIONS.keys())[0],
                    interactive=True,
                )
            with gr.Group():
                content_class_input = gr.Dropdown(
                    AVAILABLE_CONTENTCLASSES,
                    label="Content class",
                    info="Type of the images to be generated.",
                    interactive=True,
                )
                style_image_input = gr.Image(
                    label="Style image", type="filepath", sources="upload"
                )
    with gr.Accordion(label="Data exchange (dev view)", open=False) as dev_view:
        with gr.Row():
            request_display = gr.JSON(label="Request", max_height=None)
            response_display = gr.JSON(label="Response", max_height=None)

    generate.click(
        fn=call_api,
        inputs=[
            api_handler,
            api_key_input,
            scene_file_input,
            prompt_input,
            hero_input,
            camera_input,
            image_count_input,
            seed_input,
            resolution_input,
            content_class_input,
            style_image_input,
        ],
        outputs=[result, request_display, response_display],
    )

if __name__ == "__main__":
    demo.launch(inbrowser=True)
