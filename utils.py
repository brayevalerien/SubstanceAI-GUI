import os
from datetime import datetime
import gradio as gr
from hashlib import sha256


def save_image(image_data, output_directory: str = "./output/") -> str:
    """
    Given raw image bytes, saves them to a new png file inside the specified output directory.

    Args:
        image_data: image bytes
        output_directory (str): directory where the image should be saved.

    Returns:
        str: path to the saved image.
    """
    output_directory = os.path.join(
        output_directory, datetime.today().strftime("%Y-%m-%d")
    )
    os.makedirs(output_directory, exist_ok=True)
    img_num = 1
    filename = f"substanceai_{img_num:05d}.png"
    filepath = os.path.join(output_directory, filename)
    while os.path.exists(filepath):
        img_num += 1
        if img_num >= 100000:
            raise gr.Error(
                f"Cannot save the image because the output directory ({output_directory}) is full.",
                title="Save Error",
            )
        filename = f"substanceai_{img_num:05d}.png"
        filepath = os.path.join(output_directory, filename)
    with open(filepath, "wb") as f:
        f.write(image_data)
        print(f"Saved image at {filepath}")
    return filepath


def hash_files(files: str, buffer_size: int = 65536) -> str:
    """
    Computes the hash of a file.
    Adapted from: https://stackoverflow.com/a/22058673

    Args:
        files (list[str]): a list of pathes to the files, that can be relative or absolute.
        buffer_size (int): size, in bytes, of the chunks in which the file will be split during computation. Set to None to read the whole file at once.

    Returns:
        str: the computed hash.
    """
    hash = sha256()
    for path in files:
        if not path is None:
            with open(path, "rb") as file:
                while True:
                    bytes = file.read(buffer_size)
                    if not bytes:
                        break
                    hash.update(bytes)
    return hash.hexdigest()
