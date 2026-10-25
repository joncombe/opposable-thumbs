import pytest
from PIL import Image

from opposable_thumbs import Config
from opposable_thumbs.operations import OPERATIONS

from helpers import open_result

# an example of valid arguments for every operation, and the size it makes
# from the 40 x 30 test image
VALID = {
    "autocontrast": ("", (40, 30)),
    "blur": ("", (40, 30)),
    "brightness": (",1.2", (40, 30)),
    "color": (",1.2", (40, 30)),
    "colorize": (",000000,ff0000", (40, 30)),
    "contour": ("", (40, 30)),
    "contrast": (",1.2", (40, 30)),
    "crop": (",0,0,10,10", (10, 10)),
    "cropratio": (",1", (30, 30)),
    "emboss": ("", (40, 30)),
    "equalize": ("", (40, 30)),
    "fliphoriz": ("", (40, 30)),
    "flipvert": ("", (40, 30)),
    "gblur": (",2", (40, 30)),
    "grayscale": ("", (40, 30)),
    "invert": ("", (40, 30)),
    "posterize": (",2", (40, 30)),
    "resize": (",20,10", (20, 10)),
    "resizemax": (",20,20", (20, 15)),
    "resizemin": (",20,20", (27, 20)),
    "resizepc": (",0.5,0.5", (20, 15)),
    "rotate": (",90", (30, 40)),
    "circle": ("", (30, 30)),
    "fit": (",20,20", (20, 20)),
    "pad": (",20,20", (20, 20)),
    "rounded": (",5", (40, 30)),
    "unsharp": (",2,150,3", (40, 30)),
    "sharpness": (",1.2", (40, 30)),
    "solarize": (",100", (40, 30)),
}

SOURCES = [
    "rgb.png",
    "rgb.jpg",
    "rgba.png",
    "la.png",
    "grey16.png",
    "cmyk.jpg",
    "palette.gif",
    "bilevel.bmp",
    "photo.tif",
]


def test_every_operation_is_tested():
    assert set(VALID) == set(OPERATIONS)


@pytest.mark.parametrize("name", sorted(VALID))
def test_operation(thumb, name):
    args, size = VALID[name]
    assert open_result(thumb("rgb.png", f"p={name}{args}")).size == size


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("name", sorted(VALID))
def test_operation_on_every_image_mode(thumb, source, name):
    args, size = VALID[name]
    assert thumb(source, f"p={name}{args}").status == 200


@pytest.mark.parametrize(
    "op",
    [
        "brightness",
        "brightness,x",
        "colorize,zz,qq",
        "colorize,fff",
        "crop,1,2",
        "cropratio,0",
        "cropratio,-1",
        "cropratio,x",
        "cropratio,nan",
        "gblur,x",
        "posterize,0",
        "posterize,9",
        "posterize,x",
        "resize,x,1",
        "resizemax,10,0",
        "resizemax,0,0",
        "resizepc,inf,1",
        "fit,x,1",
        "pad,x,1",
        "pad,10,10,zz",
        "rounded,x",
        "rounded,-1",
        "unsharp,x",
        "unsharp,-1",
        "unsharp,2,x",
        "resizepc,nan,1",
        "rotate,x",
        "rotate,1.5",
        "rotate,15,zz",
        "solarize,x",
    ],
)
def test_invalid_arguments(thumb, op):
    name = op.split(",")[0]
    result = thumb("rgb.png", f"p={op}")
    assert (result.status, result.errors) == (400, (f"Invalid {name} arguments",))


@pytest.mark.parametrize(
    "op, error",
    [
        ("resize,5000,10", "Output larger than 4000px (max_output_size)"),
        ("resizepc,1000,1", "Output larger than 4000px (max_output_size)"),
        ("crop,100,100,200,200", "Crop box outside the image"),
        ("crop,-20,0,-10,10", "Crop box outside the image"),
        ("crop,0,0,0,10", "Output smaller than 1px"),
        ("crop,10,10,0,0", "Output smaller than 1px"),
        ("resize,0,10", "Output smaller than 1px"),
        ("resizepc,0,0", "Output smaller than 1px"),
        ("resizepc,-1,1", "Output smaller than 1px"),
        ("cropratio,inf", "Output smaller than 1px"),
        ("cropratio,1e9", "Output smaller than 1px"),
        ("gblur,101", "gblur radius larger than 100 (max_blur_radius)"),
        ("unsharp,101", "unsharp radius larger than 100 (max_blur_radius)"),
        ("fit,5000,10", "Output larger than 4000px (max_output_size)"),
        ("fit,0,10", "Output smaller than 1px"),
        ("pad,10,5000", "Output larger than 4000px (max_output_size)"),
    ],
)
def test_limits(thumb, op, error):
    result = thumb("rgb.png", f"p={op}")
    assert (result.status, result.errors) == (400, (error,))


def test_limits_come_from_config(images, thumb):
    config = Config(
        signed_urls=False,
        roots={"images": images},
        max_output_size=20,
        max_blur_radius=1,
    )
    assert thumb("rgb.png", "p=resize,21,10", config=config).errors == (
        "Output larger than 20px (max_output_size)",
    )
    assert thumb("rgb.png", "p=gblur,2", config=config).errors == (
        "gblur radius larger than 1 (max_blur_radius)",
    )
    # a 40 x 30 image rotated 30 degrees is about 50 x 46
    assert thumb("rgb.png", "p=resize,16,12|rotate,30", config=config).status == 200
    assert thumb("rgb.png", "p=rotate,30", config=config).errors == (
        "Output larger than 20px (max_output_size)",
    )


def test_every_operation_error_is_reported(thumb):
    result = thumb("rgb.png", "p=resize,x,1|rotate,y|gblur,500")
    assert result.errors == (
        "Invalid resize arguments",
        "Invalid rotate arguments",
        "gblur radius larger than 100 (max_blur_radius)",
    )


def test_crops_are_not_limited_by_max_output_size(images, thumb):
    # crops can't make an image larger, so a crop of a source bigger than
    # max_output_size works, e.g. before a resize
    config = Config(signed_urls=False, roots={"images": images}, max_output_size=20)
    result = thumb(
        "rgb.png", "p=crop,0,0,40,30|cropratio,1|resize,10,10", config=config
    )
    assert open_result(result).size == (10, 10)


@pytest.mark.parametrize(
    "box, size",
    [
        ("-10,-10,20,20", (20, 20)),
        ("30,20,100,100", (10, 10)),
        ("-100,-100,100,100", (40, 30)),
    ],
)
def test_crop_box_is_clamped_to_the_image(thumb, box, size):
    assert open_result(thumb("rgb.png", f"p=crop,{box}")).size == size


def test_crops_run_first(thumb):
    # flipping then cropping the left half would give the white half; the
    # crop runs first, so the red half is cropped and then flipped
    image = open_result(thumb("rgb.png", "p=fliphoriz|crop,0,0,20,30"))
    assert image.convert("RGB").getpixel((5, 5)) == (255, 0, 0)


def test_operations_run_in_order(thumb):
    image = open_result(thumb("rgb.png", "p=resize,10,10|resizepc,2,1"))
    assert image.size == (20, 10)


@pytest.mark.parametrize(
    "name", sorted(set(VALID) - {"grayscale", "colorize", "rotate", "crop"})
)
@pytest.mark.parametrize("alpha", [0, 128, 255])
def test_alpha_is_kept(images, thumb, name, alpha):
    Image.new("RGBA", (40, 30), (200, 50, 50, alpha)).save(images / "alpha.png")
    args, _ = VALID[name]
    image = open_result(thumb("alpha.png", f"p={name}{args}"))
    assert image.mode == "RGBA"
    assert image.getpixel((image.width // 2, image.height // 2))[3] == alpha


# what the operations do, beyond the size they make


def pixels(thumb, query):
    return open_result(thumb("rgb.png", f"{query}&format=png")).convert("RGBA")


def test_rotate_keeps_the_whole_image(thumb):
    image = pixels(thumb, "p=rotate,90")
    # the red left half is now at the bottom, and nothing is cut off
    assert image.size == (30, 40)
    assert image.getpixel((15, 35)) == (255, 0, 0, 255)
    assert image.getpixel((15, 5)) == (255, 255, 255, 255)


@pytest.mark.parametrize(
    "query, corner",
    [
        ("p=rotate,30", (0, 0, 0, 0)),
        ("p=rotate,30,ff0000", (255, 0, 0, 255)),
        ("p=rotate,30,0000ff80", (0, 0, 255, 128)),
    ],
)
def test_rotate_fills_the_corners(thumb, query, corner):
    assert pixels(thumb, query).getpixel((0, 0)) == corner


def test_rotate_by_a_right_angle_adds_no_transparency(thumb):
    image = open_result(thumb("rgb.png", "p=rotate,90&format=png"))
    assert image.mode == "RGB"


def test_fit_crops_the_centre(thumb):
    # 40 x 30, red left half: the centre 20 x 20 of a 27 x 20 resize
    image = pixels(thumb, "p=fit,20,20")
    assert image.size == (20, 20)
    assert image.getpixel((1, 10))[:3] == pytest.approx((255, 0, 0), abs=10)
    assert image.getpixel((18, 10))[:3] == pytest.approx((255, 255, 255), abs=10)


@pytest.mark.parametrize(
    "query, source, edge",
    [
        ("p=pad,40,40", "rgb.png", (255, 255, 255, 255)),
        ("p=pad,40,40,0000ff", "rgb.png", (0, 0, 255, 255)),
        ("p=pad,40,40,0000ff80", "rgb.png", (0, 0, 255, 128)),
        ("p=pad,40,40", "rgba.png", (255, 255, 255, 0)),
    ],
)
def test_pad(thumb, query, source, edge):
    image = open_result(thumb(source, f"{query}&format=png")).convert("RGBA")
    assert image.size == (40, 40)
    assert image.getpixel((20, 1)) == edge


@pytest.mark.parametrize("name, size", [("circle", (30, 30)), ("rounded,8", (40, 30))])
def test_shapes_have_transparent_corners(thumb, name, size):
    image = pixels(thumb, f"p={name}")
    assert image.size == size
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((size[0] // 2, size[1] // 2))[3] == 255


def test_shapes_are_flattened_onto_white_for_jpeg(thumb):
    # JPEG blurs colours a little, even at high quality
    image = open_result(thumb("rgb.png", "p=circle&format=jpeg&quality=95"))
    assert image.getpixel((0, 0)) == pytest.approx((255, 255, 255), abs=12)
