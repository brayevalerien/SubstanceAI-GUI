import os
import gradio as gr
from api_manager import AVAILABLE_RESOLUTIONS, compose_2D_3D, upload_to_space

VERSION = "0.1.0 (beta)"
TITLE = f"SubstanceAI GUI v{VERSION}"

with gr.Blocks(title=TITLE, analytics_enabled=False, theme='Zarkel/IBM_Carbon_Theme') as demo:
    with gr.Row():
        with gr.Column(scale=2):
            result = gr.Image(label="Result", format="png", type="filepath", interactive=False)
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
                    minimum=1, maximum=16,
                    step=1, interactive=True
                )
                seed_input = gr.Number(
                    label="Seed",
                    
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
        fn = compose_2D_3D,
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
    demo.launch()