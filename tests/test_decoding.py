"""Reduced decoding of JPEGs, and that it gives the same thumbnails."""

from io import BytesIO

import pytest
from PIL import Image, ImageChops, ImageOps, ImageStat
from PIL.JpegImagePlugin import JpegImageFile

from opposable_thumbs import Config, handle_request
from opposable_thumbs.operations import reduction_limit

# the planner: how many times smaller a 3000 x 2000 image could be


@pytest.mark.parametrize(
    "operations, limit",
    [
        ([["fit", "300", "200"]], 10),
        ([["fit", "300", "300"]], 2000 / 300),
        ([["resize", "300", "300"]], 2000 / 300),
        ([["resizemin", "300", "300"]], 2000 / 300),
        ([["resizemax", "300", "300"]], 3000 / 300),
        ([["pad", "300", "300"]], 3000 / 300),
        # cropratio,1 keeps the centre 2000 x 2000
        ([["cropratio", "1"], ["resize", "100", "100"]], 20),
        ([["resize", "100", "100"], ["cropratio", "1"]], 20),
        ([["grayscale"], ["invert"], ["fit", "300", "200"]], 10),
        # only the first resize counts
        ([["fit", "300", "200"], ["resize", "10", "10"]], 10),
        # a crop keeps the part of the image in its box, whatever order
        ([["crop", "0", "0", "1000", "1000"], ["resize", "100", "100"]], 10),
        ([["resize", "100", "100"], ["crop", "0", "0", "1000", "1000"]], 10),
        ([["crop", "2000", "0", "4000", "2000"], ["fit", "100", "100"]], 10),
        (
            [
                ["crop", "0", "0", "2000", "1000"],
                ["cropratio", "1"],
                ["fit", "100", "100"],
            ],
            10,
        ),
        # upscaling can't use a smaller image
        ([["resize", "6000", "4000"]], 1),
    ],
)
def test_reduction_limit(operations, limit):
    assert reduction_limit(operations, 3000, 2000) == pytest.approx(limit)


@pytest.mark.parametrize(
    "operations",
    [
        [],
        [["grayscale"]],
        # these depend on the image's scale, so nothing is reduced
        [["resizepc", "0.1", "0.1"]],
        [["gblur", "2"], ["fit", "300", "200"]],
        [["rotate", "90"], ["fit", "300", "200"]],
        [["circle"], ["fit", "300", "200"]],
        # invalid arguments are left for the operation to report
        [["fit", "x", "1"]],
        [["fit", "0", "0"]],
        [["cropratio", "x"], ["fit", "300", "200"]],
        [["crop", "x", "0", "10", "10"], ["fit", "300", "200"]],
        # a box outside the image is reported when the crop runs
        [["crop", "4000", "0", "5000", "10"], ["fit", "300", "200"]],
    ],
)
def test_no_reduction(operations):
    assert reduction_limit(operations, 3000, 2000) == 1


# decoding


@pytest.fixture
def photos(images):
    """A noisy 1200 x 800 photo as a JPEG, and its decoded pixels as a PNG,
    which is never reduced."""
    photo = Image.effect_noise((1200, 800), 40).convert("RGB")
    photo.paste((200, 50, 50), (0, 0, 600, 800))
    photo.save(images / "photo.jpg", quality=95)
    with Image.open(images / "photo.jpg") as decoded:
        decoded.save(images / "photo.png")


@pytest.fixture
def drafts(monkeypatch):
    """The sizes JPEGs are asked to be decoded at."""
    calls = []
    real_draft = JpegImageFile.draft

    def draft(self, mode, size):
        calls.append(size)
        return real_draft(self, mode, size)

    monkeypatch.setattr(JpegImageFile, "draft", draft)
    return calls


def thumbnail(thumb, name, p):
    result = thumb(name, f"p={p}&format=png")
    assert result.status == 200, result.body
    return Image.open(BytesIO(result.body)).convert("RGB")


@pytest.mark.parametrize(
    "p",
    [
        "fit,100,100",
        "cropratio,1|resize,100,100",
        "resizemax,150,150|grayscale",
        "pad,100,100",
        "fit,100,100|gblur,1",
        # crop boxes are scaled to match. the box's edges cross the boundary
        # between the red and the noise, so a misplaced box would show
        "crop,100,50,1100,750|resize,100,70",
        "resize,100,100|crop,550,0,1150,600",
        "crop,0,0,1200,800|cropratio,1|fit,100,100",
        "crop,590,0,1200,800|fit,60,80",
        "crop,-50,-50,700,900|resizemax,100,100",
    ],
)
def test_reduced_decoding_gives_the_same_thumbnail(photos, thumb, drafts, p):
    reduced = thumbnail(thumb, "photo.jpg", p)
    assert drafts, "the JPEG wasn't reduced"
    full = thumbnail(thumb, "photo.png", p)
    assert reduced.size == full.size
    difference = ImageStat.Stat(ImageChops.difference(reduced, full))
    assert max(difference.mean) < 1.5


def test_scale_dependent_operations_decode_in_full(photos, thumb, drafts):
    thumbnail(thumb, "photo.jpg", "gblur,2|fit,100,100")
    thumbnail(thumb, "photo.jpg", "rotate,10|fit,100,100")
    assert drafts == []


def test_small_reductions_are_skipped(photos, thumb, drafts):
    # 1200 x 800 to 500 wide is less than 2 x 2 smaller
    thumbnail(thumb, "photo.jpg", "resizemax,500,500")
    assert drafts == []


def test_reduction_uses_the_upright_size(images, thumb, drafts):
    # stored 1200 x 800 but displayed 800 x 1200: fit,100,300 needs 4 times
    # smaller, so it decodes at no less than 600 x 400 (stored orientation)
    photo = Image.effect_noise((1200, 800), 40).convert("RGB")
    exif = Image.Exif()
    exif[0x0112] = 6
    photo.save(images / "sideways.jpg", exif=exif.tobytes())
    assert thumbnail(thumb, "sideways.jpg", "fit,100,300").size == (100, 300)
    assert drafts == [(600, 400)]


def test_reduced_crop_uses_the_upright_size(images, thumb, drafts):
    # upright 800 x 1200 with a red top half, stored sideways as 1200 x 800.
    # the crop box is in upright pixels, so it is scaled the upright way
    upright = Image.effect_noise((800, 1200), 40).convert("RGB")
    upright.paste((200, 50, 50), (0, 0, 800, 600))
    exif = Image.Exif()
    exif[0x0112] = 6
    upright.transpose(Image.Transpose.ROTATE_90).save(
        images / "sideways.jpg", exif=exif.tobytes(), quality=95
    )
    with Image.open(images / "sideways.jpg") as decoded:
        ImageOps.exif_transpose(decoded).save(images / "upright.png")

    p = "crop,0,500,800,1100|resize,80,60"
    reduced = thumbnail(thumb, "sideways.jpg", p)
    assert drafts, "the JPEG wasn't reduced"
    full = thumbnail(thumb, "upright.png", p)
    assert reduced.size == full.size == (80, 60)
    difference = ImageStat.Stat(ImageChops.difference(reduced, full))
    assert max(difference.mean) < 1.5


def test_png_is_never_reduced(photos, images, drafts):
    config = Config(roots={"images": images}, signed_urls=False)
    handle_request(config, "file=images/photo.png&p=fit,100,100")
    assert drafts == []
