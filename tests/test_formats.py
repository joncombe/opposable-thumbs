import pytest
from PIL import Image

from opposable_thumbs import Config, save_thumbnail

from helpers import open_result


@pytest.mark.parametrize(
    "source, format, content_type",
    [
        ("rgb.png", "PNG", "image/png"),
        ("rgb.jpg", "JPEG", "image/jpeg"),
        ("palette.gif", "GIF", "image/gif"),
        ("bilevel.bmp", "BMP", "image/bmp"),
        ("photo.tif", "TIFF", "image/tiff"),
        ("phone.jpg", "JPEG", "image/jpeg"),  # MPO
    ],
)
def test_output_format_follows_source(thumb, source, format, content_type):
    result = thumb(source)
    assert open_result(result).format == format
    assert result.content_type == content_type


@pytest.mark.parametrize(
    "value, format",
    [
        ("jpeg", "JPEG"),
        ("JPG", "JPEG"),
        ("png", "PNG"),
        ("webp", "WEBP"),
        ("gif", "GIF"),
        ("bmp", "BMP"),
        ("tiff", "TIFF"),
        ("tif", "TIFF"),
    ],
)
def test_format_parameter(thumb, value, format):
    result = thumb("rgb.png", f"format={value}")
    assert open_result(result).format == format
    assert result.content_type == f"image/{format.lower()}"


def test_transparency_is_flattened_onto_white_for_jpeg(thumb):
    image = open_result(thumb("rgba.png", "format=jpeg"))
    assert image.mode == "RGB"
    # 50% red over white
    assert image.getpixel((0, 0)) == pytest.approx((255, 127, 127), abs=2)


def test_16_bit_grey_is_scaled_not_clipped(thumb):
    assert open_result(thumb("grey16.png")).getpixel((0, 0)) == 128


def test_quality(thumb, images):
    big = Image.effect_noise((100, 100), 60).convert("RGB")
    big.save(images / "noise.png")
    sizes = [
        len(thumb("noise.png", f"format={format}&quality={quality}").body)
        for format in ("jpeg", "webp")
        for quality in (10, 90)
    ]
    assert sizes[0] < sizes[1] and sizes[2] < sizes[3]


def test_quality_is_ignored_for_other_formats(thumb):
    assert thumb("rgb.png", "quality=10").body == thumb("rgb.png").body


# EXIF orientation


def test_exif_orientation_is_applied(thumb):
    image = open_result(thumb("sideways.jpg", "format=png"))
    assert image.size == (20, 40)
    assert image.getpixel((10, 2))[:3] == pytest.approx((255, 0, 0), abs=5)
    # the output has no orientation tag for a browser to apply again
    assert 0x0112 not in image.getexif()


def test_exif_orientation_can_be_turned_off(images, thumb):
    config = Config(
        signed_urls=False, roots={"images": images}, apply_exif_orientation=False
    )
    assert open_result(thumb("sideways.jpg", config=config)).size == (40, 20)


def test_crop_uses_upright_coordinates(thumb):
    image = open_result(thumb("sideways.jpg", "p=crop,0,0,20,20&format=png"))
    assert image.getpixel((10, 10))[:3] == pytest.approx((255, 0, 0), abs=5)


def test_broken_exif_is_ignored(images, thumb):
    Image.new("RGB", (40, 20)).save(images / "bad.jpg", exif=b"Exif\x00\x00garbage")
    assert open_result(thumb("bad.jpg")).size == (40, 20)


# save_thumbnail


@pytest.mark.parametrize(
    "name, format, expected",
    [
        ("out.jpg", None, "JPEG"),
        ("out.webp", None, "WEBP"),
        ("out.jpg", "png", "PNG"),
        ("out.dat", None, "PNG"),
        ("out", None, "PNG"),
    ],
)
def test_save_thumbnail_format(images, config, tmp_path, name, format, expected):
    path = tmp_path / name
    save_thumbnail(config, path, file="images/rgb.png", format=format)
    with Image.open(path) as image:
        assert image.format == expected


def test_save_thumbnail_flattens_for_jpeg(images, config, tmp_path):
    save_thumbnail(config, tmp_path / "out.jpg", file="images/rgba.png")
    with Image.open(tmp_path / "out.jpg") as image:
        assert image.mode == "RGB"


def test_animated_gif_uses_the_first_frame(images, thumb):
    # also checks the file is closed: Pillow keeps files with several frames
    # open, and a warning about it fails the tests
    red, blue = Image.new("RGB", (40, 30), "red"), Image.new("RGB", (40, 30), "blue")
    red.save(images / "anim.gif", save_all=True, append_images=[blue])
    image = open_result(thumb("anim.gif", "format=png"))
    assert image.convert("RGB").getpixel((5, 5)) == (255, 0, 0)


def test_truncated_image_is_404(images, thumb):
    Image.effect_noise((100, 100), 50).convert("RGB").save(images / "full.jpg")
    data = (images / "full.jpg").read_bytes()
    (images / "cut.jpg").write_bytes(data[: len(data) // 2])
    result = thumb("cut.jpg", "p=blur")
    assert (result.status, result.errors) == (404, ("Failed to open image",))
