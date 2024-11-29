import os
import gradio as gr

VERSION = "0.1.0 (beta)"
TITLE = f"SubstanceAI GUI v{VERSION}"

# TODO extract available resolutions and their handling in a separate module
# Valid resolutions for the Substance API, see:
# https://s3d.adobe.io/v1beta/docs#/paths/v1beta-3dscenes-compose/post#request-body
AVAILABLE_RESOLUTIONS = {
    "2048 × 2048 | 1:1": (2048, 2048),
    "2304 × 1792 | 4:3": (2304, 1792),
    "1792 × 2304 | 3:4": (1792, 2304),
    "2688 × 1536 | 16:9": (2688, 1536),
    "1344 × 768  | 7:4": (1344, 768),
    "1152 × 896  | 9:7": (1152, 896),
    "896  × 1152 | 7:9": (896, 1152),
    "1024 × 1024 | 1:1": (1024, 1024),
}

with gr.Blocks(title=TITLE, analytics_enabled=False, theme='Zarkel/IBM_Carbon_Theme') as demo:
    with gr.Row():
        with gr.Column(scale=2):
            gr.Image(label="Result", format="png", interactive=False)
            with gr.Group() as input_group:
                blend_file_input = gr.File(label="Upload Blender file")
                with gr.Row():
                    with gr.Column(scale=2):
                        prompt_input = gr.TextArea(label="Prompt", placeholder="Write what you want to see in the image here.")
                    with gr.Column(scale=1):
                        hero_input = gr.Textbox(
                            label="Hero object",
                            info="Exact name of the product in the Blender scene",
                            interactive=True
                        )
                        camera_input = gr.Textbox(
                            label="Camera",
                            info="Exact name of the camera in the Blender scene", value="Camera", interactive=True
                        )
                with gr.Row():
                    generate = gr.Button(value="Generate", variant="primary")
            with gr.Accordion(label="Data exchange (dev view)", open=True) as dev_view:
                with gr.Row():
                    request_display = gr.JSON(label="Request", max_height=None)
                    response_display = gr.JSON(label="Response", max_height=None)
        
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
                    minimum=1, maximum=16,
                    step=1, interactive=True
                )
                seed_input = gr.Number(
                    label="Seed",
                    
                )    
            with gr.Group():
                resolution_input = gr.Radio(
                    label="Resolution", choices=AVAILABLE_RESOLUTIONS.keys(),
                    value=list(AVAILABLE_RESOLUTIONS.keys())[0]
                )
            with gr.Group():
                gr.Markdown("Please note that the style image is an upcoming feature and is **not implemented yet**. Uploading an image here will have no effect.")
                gr.Image(label="Style image")


if __name__ == "__main__":
    demo.launch()