import subprocess


def generate_trdg_images() -> None:
    """
    Use trdg package to generate images with text for training model.
    """
    command = [
        "trdg",
        "--output_dir", "training_data/chinese_data/trdg_synthetic_images",  # The output directory.
        "--language", "cn",  # The language to use.
        "--count", "20",  # The number of images to be created.
        "--length", "18",  # Define how many words should be included in each generated sample.
        "--random",  # Define if the produced string will have variable word count (with --length being the maximum).
        "--format", "100",  # Define the height of the produced images if horizontal, else the width.
        "--width", "1900",  # Define the width of the resulting image
        "--thread_count", "6",  # Define the number of thread to use for image generation.
        "--background", "3",  # Background to use. 0: Gaussian Noise, 1: Plain white, 2: Quasi crystal, 3: Image.
        "--image_dir", "training_data/#Background_images",  # Image directory to use when background is set to image.
        "--output_bboxes", "1",  # Define if the generator will return bounding boxes for the text.
        "--text_color", "#FFFFFF",  # Text's color. "#000000,#FFFFFF" for black to white range.
        "--space_width", "0",  # Define the width of the spaces between words
        "--margins", "15,15,15,15",  # Define the margins around the text when rendered. In pixels.
        "--fit",  # Apply a tight crop around the rendered text
        # Rarely needed options.
        # "--character_spacing", "0",  # Define the width of the spaces between characters. 2 means two pixels.
        # "--random_sequences",  # Use random sequences as the source text for the generation.
        # "--font_dir", "data/#Fonts",  # Define a font directory to be used.
        # "--word_split",  # Split on words instead of on characters.
    ]
    print(f"Command: {' '.join(command)}")
    try:
        # Run the command using subprocess.run().
        subprocess.run(command)
    except Exception as error:
        print(f"An error occurred. Error: {error}")


if __name__ == '__main__':
    generate_trdg_images()
