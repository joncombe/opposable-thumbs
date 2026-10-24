import os

from PIL import Image, ImageOps

# formats an image can be returned in, and their MIME types
OUTPUT_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
}

# other names accepted by format=
FORMAT_ALIASES = {"JPG": "JPEG", "TIF": "TIFF"}

# output format for a source that isn't in OUTPUT_FORMATS, when there is no
# format=. MPO is a JPEG with extra images, e.g. from iPhones. any other
# format is returned as PNG
SOURCE_OUTPUT_FORMATS = {"MPO": "JPEG"}

# output formats that quality= applies to
QUALITY_FORMATS = ("JPEG", "WEBP")


def output_format_for(source_format):
    # the format an image is returned in when there is no format=
    if source_format in OUTPUT_FORMATS:
        return source_format
    return SOURCE_OUTPUT_FORMATS.get(source_format, "PNG")


def format_for_path(path):
    # the output format a file extension stands for, e.g. .jpg is JPEG
    extension = os.path.splitext(path)[1].lower()
    format = Image.registered_extensions().get(extension)
    return format if format in OUTPUT_FORMATS else None


def apply_exif_orientation(image):
    # rotate / flip the image upright, as browsers display it. a broken EXIF
    # block leaves the image as it is
    try:
        return ImageOps.exif_transpose(image)
    except Exception:
        return image


def normalise_mode(image):
    # the operations all work on RGB, RGBA and L images, so convert anything
    # else (palette, 1-bit, 16-bit, CMYK...) to one of those, keeping any
    # transparency
    mode = image.mode
    if mode in ("RGB", "RGBA", "L"):
        return image

    if "A" in image.getbands() or "transparency" in image.info:
        return image.convert("RGBA")
    if mode.startswith("I"):
        # 16-bit grayscale: scale down rather than clip everything to white
        return image.convert("I").point(lambda v: v / 256).convert("L")
    return image.convert("RGB")


def apply_without_alpha(image, operation):
    # some ImageOps functions refuse an alpha channel, so apply them to the
    # colour channels and put the alpha back afterwards
    if image.mode != "RGBA":
        return operation(image)

    alpha = image.getchannel("A")
    result = operation(image.convert("RGB"))
    result.putalpha(alpha)
    return result


def prepare_for_format(image, format):
    # JPEG has no transparency, so flatten onto white rather than fail
    if format == "JPEG" and image.mode == "RGBA":
        flattened = Image.new("RGB", image.size, "white")
        flattened.paste(image, mask=image.getchannel("A"))
        return flattened

    return image
