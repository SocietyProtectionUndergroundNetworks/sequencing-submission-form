import os


def get_or_create_thumbnail(file_path, size=(240, 240)):
    """
    Returns the path to a cached thumbnail for the given image, generating
    it into a sibling 'thumbnails' directory if it doesn't exist yet.
    """
    from PIL import Image

    abs_path = os.path.abspath(file_path)
    photo_dir = os.path.dirname(abs_path)
    thumb_dir = os.path.join(photo_dir, "thumbnails")
    thumb_path = os.path.join(thumb_dir, os.path.basename(abs_path))

    if not os.path.exists(thumb_path):
        os.makedirs(thumb_dir, exist_ok=True)
        with Image.open(abs_path) as img:
            img = img.convert("RGB")
            img.thumbnail(size)
            img.save(thumb_path, "JPEG", quality=75)

    return thumb_path
