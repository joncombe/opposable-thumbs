"""The operations that can be listed in p=.

Each operation takes the image, the arguments given after its name in p= (as
strings) and the Config, and returns the new image. It raises ValueError,
IndexError or ArithmeticError for invalid arguments, which is reported as
"Invalid <name> arguments", or OperationError for a more specific problem.
"""

import math

from PIL import (
    Image,
    ImageChops,
    ImageColor,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageOps,
)

from .imaging import apply_without_alpha

# name -> function, filled in by @operation
OPERATIONS = {}

# run before every other operation, whatever order they are given in
CROP_OPERATIONS = set()


class OperationError(Exception):
    """An operation's arguments can't be used, e.g. they are over a limit."""


def operation(name, crop=False):
    def register(func):
        OPERATIONS[name] = func
        if crop:
            CROP_OPERATIONS.add(name)
        return func

    return register


def check_output_size(width, height, config):
    # refuse to create an image wider or taller than max_output_size, e.g.
    # from resize,20000,20000. only for operations that can make an image
    # larger: crops can't, and max_source_pixels limits the source
    if width > config.max_output_size or height > config.max_output_size:
        raise OperationError(
            f"Output larger than {config.max_output_size}px (max_output_size)"
        )
    check_not_empty(width, height)


def check_not_empty(width, height):
    # an empty image can't be saved
    if width < 1 or height < 1:
        raise OperationError("Output smaller than 1px")


# resizes first shrink by a whole number quickly, to no less than this many
# times the final size, then finish with LANCZOS: about twice as fast, and
# the difference can't be seen
REDUCING_GAP = 3.0


def resize(image, width, height, config, box=None):
    # resize to width x height, optionally only the part of the image in box
    check_output_size(width, height, config)
    return image.resize(
        (width, height),
        resample=Image.Resampling.LANCZOS,
        box=box,
        reducing_gap=REDUCING_GAP,
    )


def size_argument(args, config):
    # (width, height) from the first two arguments, checked against the limits
    width, height = int(args[0]), int(args[1])
    check_output_size(width, height, config)
    return width, height


def colour_argument(colour, image):
    # (image, colour) for a hex colour argument (without #) in the image's
    # mode. a colour with transparency (8 hex digits) needs an RGBA image
    if ImageColor.getcolor(f"#{colour}", "RGBA")[3] < 255 and image.mode != "RGBA":
        image = image.convert("RGBA")
    return image, ImageColor.getcolor(f"#{colour}", image.mode)


def mask_shape(image, draw):
    # make the image transparent outside a shape. draw(ImageDraw, scale) draws
    # the shape on a mask `scale` times larger than the image, which is scaled
    # down so the edges are smooth. the scale is smaller for big images, to
    # limit the mask's memory
    width, height = image.size
    scale = max(1, min(4, 8000 // max(width, height)))
    mask = Image.new("L", (width * scale, height * scale), 0)
    draw(ImageDraw.Draw(mask), scale)
    mask = mask.resize(image.size, resample=Image.Resampling.LANCZOS)

    # keep any transparency the image already has
    image = image.convert("RGBA")
    image.putalpha(ImageChops.multiply(mask, image.getchannel("A")))
    return image


def cropratio_size(width, height, ratio):
    # the size of the largest box with this width / height ratio that fits
    # in width x height
    if width / height > ratio:
        return height * ratio, height
    return width, width / ratio


@operation("crop", crop=True)
def crop(image, args, config):
    # crop to a box, in pixels. the part of the box outside the image is
    # ignored, so it can't make the image larger
    left, top, right, bottom = [int(a) for a in args[:4]]
    check_not_empty(right - left, bottom - top)
    left, top = max(left, 0), max(top, 0)
    right, bottom = min(right, image.width), min(bottom, image.height)
    if right <= left or bottom <= top:
        raise OperationError("Crop box outside the image")
    return image.crop((left, top, right, bottom))


def scale_crop(args, x_scale, y_scale):
    # crop's arguments for an image decoded x_scale x y_scale times smaller,
    # as the box is given in the source's pixels
    left, top, right, bottom = [int(a) for a in args[:4]]
    scaled = [
        round(left / x_scale),
        round(top / y_scale),
        round(right / x_scale),
        round(bottom / y_scale),
    ]
    # a box that isn't empty mustn't become empty by rounding
    if right > left:
        scaled[2] = max(scaled[2], scaled[0] + 1)
    if bottom > top:
        scaled[3] = max(scaled[3], scaled[1] + 1)
    return scaled


@operation("cropratio", crop=True)
def cropratio(image, args, config):
    # crop the centre of the image to a width / height ratio
    width, height = image.size
    orig_ratio = width / height
    target_ratio = float(args[0])
    if not target_ratio > 0:
        raise ValueError("ratio must be positive")

    if orig_ratio > target_ratio:
        # same height, change width
        target_width = int(round(height * target_ratio))
        left = int(round((width / 2) - (target_width / 2)))
        check_not_empty(target_width, height)
        return image.crop((left, 0, left + target_width, height))

    if target_ratio > orig_ratio:
        # same width, change height
        target_height = int(round(width / target_ratio))
        top = int(round((height / 2) - (target_height / 2)))
        check_not_empty(width, target_height)
        return image.crop((0, top, width, top + target_height))

    return image


@operation("autocontrast")
def autocontrast(image, args, config):
    return apply_without_alpha(image, ImageOps.autocontrast)


@operation("blur")
def blur(image, args, config):
    return image.filter(ImageFilter.BLUR)


@operation("brightness")
def brightness(image, args, config):
    return ImageEnhance.Brightness(image).enhance(float(args[0]))


@operation("color")
def color(image, args, config):
    return ImageEnhance.Color(image).enhance(float(args[0]))


@operation("circle")
def circle(image, args, config):
    # crop the centre to a square, then make it transparent outside a circle
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    return mask_shape(
        image,
        lambda draw, scale: draw.ellipse(
            (0, 0, side * scale - 1, side * scale - 1), fill=255
        ),
    )


@operation("colorize")
def colorize(image, args, config):
    return ImageOps.colorize(
        ImageOps.grayscale(image), black=f"#{args[0]}", white=f"#{args[1]}"
    )


@operation("contour")
def contour(image, args, config):
    # without_alpha, or flat transparent areas would become opaque
    return apply_without_alpha(image, lambda i: i.filter(ImageFilter.CONTOUR))


@operation("contrast")
def contrast(image, args, config):
    return ImageEnhance.Contrast(image).enhance(float(args[0]))


@operation("emboss")
def emboss(image, args, config):
    # without_alpha, or flat opaque areas would become half transparent
    return apply_without_alpha(image, lambda i: i.filter(ImageFilter.EMBOSS))


@operation("equalize")
def equalize(image, args, config):
    return apply_without_alpha(image, ImageOps.equalize)


@operation("fit")
def fit(image, args, config):
    # resize to cover width x height, keeping the aspect ratio, then crop the
    # centre to exactly that size
    width, height = size_argument(args, config)
    # the largest box of the target's shape, in the centre
    box_width, box_height = cropratio_size(image.width, image.height, width / height)
    left = (image.width - box_width) / 2
    top = (image.height - box_height) / 2
    box = (left, top, left + box_width, top + box_height)
    return resize(image, width, height, config, box=box)


@operation("fliphoriz")
def fliphoriz(image, args, config):
    return image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)


@operation("flipvert")
def flipvert(image, args, config):
    return image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


@operation("gblur")
def gblur(image, args, config):
    radius = int(args[0])
    if radius > config.max_blur_radius:
        raise OperationError(
            f"gblur radius larger than {config.max_blur_radius} (max_blur_radius)"
        )
    return image.filter(ImageFilter.GaussianBlur(radius=radius))


@operation("grayscale")
def grayscale(image, args, config):
    return ImageOps.grayscale(image)


@operation("invert")
def invert(image, args, config):
    return apply_without_alpha(image, ImageOps.invert)


@operation("pad")
def pad(image, args, config):
    # resize to fit inside width x height, keeping the aspect ratio, then pad
    # to exactly that size with a colour: by default transparent if the image
    # has transparency, otherwise white
    width, height = size_argument(args, config)
    if len(args) > 2:
        image, colour = colour_argument(args[2], image)
    else:
        image, colour = colour_argument(
            "ffffff00" if image.mode == "RGBA" else "ffffff", image
        )
    scale = min(width / image.width, height / image.height)
    inner = resize(
        image,
        max(1, round(image.width * scale)),
        max(1, round(image.height * scale)),
        config,
    )
    padded = Image.new(image.mode, (width, height), colour)
    padded.paste(inner, ((width - inner.width) // 2, (height - inner.height) // 2))
    return padded


@operation("posterize")
def posterize(image, args, config):
    # checked here: older Pillow versions raise TypeError or accept 0
    bits = int(args[0])
    if not 1 <= bits <= 8:
        raise ValueError("bits must be 1 to 8")
    return apply_without_alpha(image, lambda i: ImageOps.posterize(i, bits))


@operation("resize")
def resize_exact(image, args, config):
    return resize(image, int(args[0]), int(args[1]), config)


@operation("resizemax")
def resizemax(image, args, config):
    # resize to fit inside width x height, keeping the aspect ratio
    orig_width, orig_height = image.size
    orig_ratio = orig_width / orig_height
    target_width, target_height = int(args[0]), int(args[1])
    target_ratio = target_width / target_height

    if orig_ratio > target_ratio:
        target_height = int(round(target_width / orig_ratio))
    elif orig_ratio < target_ratio:
        target_width = int(round(target_height * orig_ratio))

    return resize(image, target_width, target_height, config)


@operation("resizemin")
def resizemin(image, args, config):
    # resize to cover width x height, keeping the aspect ratio
    orig_width, orig_height = image.size
    orig_ratio = orig_width / orig_height
    target_width, target_height = int(args[0]), int(args[1])
    target_ratio = target_width / target_height

    if orig_ratio > target_ratio:
        target_width = int(round(target_height * orig_ratio))
    elif orig_ratio < target_ratio:
        target_height = int(round(target_width / orig_ratio))

    return resize(image, target_width, target_height, config)


@operation("resizepc")
def resizepc(image, args, config):
    x, y = image.size
    return resize(image, int(x * float(args[0])), int(y * float(args[1])), config)


@operation("rotate")
def rotate(image, args, config):
    # rotate anticlockwise, enlarging the image so none of it is cut off. the
    # corners this leaves are filled with a colour if one is given, otherwise
    # they are transparent
    angle = int(args[0])
    radians = math.radians(angle)
    cos, sin = abs(math.cos(radians)), abs(math.sin(radians))
    width, height = image.size
    # rounded, as e.g. cos(90 degrees) isn't exactly 0
    check_output_size(
        math.ceil(round(width * cos + height * sin, 6)),
        math.ceil(round(width * sin + height * cos, 6)),
        config,
    )

    if len(args) > 1:
        image, fill = colour_argument(args[1], image)
    elif angle % 90:
        image, fill = colour_argument("00000000", image)
    else:
        # a right angle leaves no corners, so the image needn't gain
        # transparency
        fill = None
    return image.rotate(
        angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=fill
    )


@operation("rounded")
def rounded(image, args, config):
    # make the corners transparent, rounded with a radius in pixels
    radius = int(args[0])
    if radius < 0:
        raise ValueError("radius can't be negative")
    width, height = image.size
    radius = min(radius, min(width, height) // 2)
    return mask_shape(
        image,
        lambda draw, scale: draw.rounded_rectangle(
            (0, 0, width * scale - 1, height * scale - 1),
            radius=radius * scale,
            fill=255,
        ),
    )


@operation("sharpness")
def sharpness(image, args, config):
    return ImageEnhance.Sharpness(image).enhance(float(args[0]))


@operation("solarize")
def solarize(image, args, config):
    threshold = int(args[0])
    return apply_without_alpha(image, lambda i: ImageOps.solarize(i, threshold))


@operation("unsharp")
def unsharp(image, args, config):
    # sharpen with an unsharp mask: radius, percent (strength) and threshold
    # (the smallest difference that is sharpened), each optional
    radius = float(args[0]) if len(args) > 0 else 2
    percent = int(args[1]) if len(args) > 1 else 150
    threshold = int(args[2]) if len(args) > 2 else 3
    if radius > config.max_blur_radius:
        raise OperationError(
            f"unsharp radius larger than {config.max_blur_radius} (max_blur_radius)"
        )
    if radius < 0 or percent < 0 or threshold < 0:
        raise ValueError("arguments can't be negative")
    mask = ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold)
    return apply_without_alpha(image, lambda i: i.filter(mask))


# reduced decoding. a JPEG can be decoded at 1/2, 1/4 or 1/8 of its size,
# which is much faster and needs much less memory. that is only the same as
# decoding it in full and shrinking it later if nothing before the resize
# depends on the image's scale, apart from crops, whose boxes are scaled

# operations unaffected by the image's scale, which may come before the resize
SCALE_FREE_OPERATIONS = {
    "autocontrast",
    "brightness",
    "color",
    "colorize",
    "contrast",
    "equalize",
    "fliphoriz",
    "flipvert",
    "grayscale",
    "invert",
    "posterize",
    "solarize",
}


def reduction_limit(operations, width, height):
    """How many times smaller a width x height image could be and still give
    the same result from these operations, e.g. 10 for a 3000 x 2000 image
    with fit,300,200. 1 if it can't be any smaller.
    """
    try:
        ordered = sorted(operations, key=lambda op: op[0] not in CROP_OPERATIONS)
        for name, *args in ordered:
            if name in SCALE_FREE_OPERATIONS:
                continue
            if name == "cropratio":
                width, height = cropratio_size(width, height, float(args[0]))
                continue
            if name == "crop":
                # the part of the box inside the image. its arguments are
                # scaled to match, see scale_crop()
                left, top, right, bottom = [int(a) for a in args[:4]]
                width = min(right, width) - max(left, 0)
                height = min(bottom, height) - max(top, 0)
                if width < 1 or height < 1:
                    return 1
                continue

            # the first operation that sets the size decides the limit
            target_width, target_height = int(args[0]), int(args[1])
            if target_width < 1 or target_height < 1:
                return 1
            ratios = (width / target_width, height / target_height)
            if name in ("resize", "resizemin", "fit"):
                # each side must still be at least the target's
                return max(1, min(ratios))
            if name in ("resizemax", "pad"):
                # the image fits inside the target, so the larger ratio
                return max(1, max(ratios))
            # anything else depends on the image's scale
            return 1
    except (ValueError, IndexError, ArithmeticError):
        # invalid arguments are reported when the operation runs
        return 1

    # no operation sets the size
    return 1
