# Operations and output

## Query parameters

A thumbnail URL's query string has a parameter for each argument of
[`make_thumbnail()`](python.md#make_thumbnail):

| Parameter | Example |
|---|---|
| `file` | `media/photo.jpg` |
| `url` | `https://cdn.example.com/photo.jpg` |
| `p` | `cropratio,1\|resize,300,300` |
| `format` | `webp` |
| `quality` | `85` |
| `s` | The [signature](configuration.md#signed-urls), added by `thumbnail_query()` |

`p` holds the operations, separated by `|`, each a name followed by its
arguments, separated by commas. Other parameters are ignored, so they don't
create extra cache entries.

Values are URL-decoded once, like any query string. If a value contains `&`,
`+`, `#` or `%`, it must be encoded, e.g. a `url` with its own query string.
[`thumbnail_query()`](python.md#thumbnail_query) does this for you. An
unencoded `+` is decoded as a space. If a parameter appears more than once,
the last value is used.

## Operations

The same operations, written two ways:

```python
operations = [("cropratio", 1.5), ("resize", 300, 200), ("sharpness", 1.2)]
```

```
p=cropratio,1.5|resize,300,200|sharpness,1.2
```

`crop` and `cropratio` always run first, in the order given, whatever their
position in the list. The other operations then run in the order given. An
unknown name or invalid arguments are an error.

| Operation | Arguments | |
|---|---|---|
| `autocontrast` | | Stretch the tones to the full range. |
| `blur` | | A light blur. |
| `brightness` | `factor` | `1` leaves the image unchanged, lower is darker, higher is brighter. |
| `circle` | | Crop the centre to a square, then make it transparent outside a circle, e.g. for avatars. |
| `color` | `factor` | Saturation. `0` is grey, `1` leaves the image unchanged. |
| `colorize` | `black,white` | Convert to grey, then map black and white to these hex colours (without `#`), e.g. `202060,ffd080`. |
| `contour` | | Trace the edges. |
| `contrast` | `factor` | `1` leaves the image unchanged. |
| `crop` | `left,top,right,bottom` | Crop to a box, in pixels. The part of the box outside the image is ignored, and a box entirely outside it is an error. |
| `cropratio` | `ratio` | Crop the centre to a width / height ratio, e.g. `1` for a square or `1.5` for 3:2. |
| `emboss` | | An embossed effect. |
| `equalize` | | Even out the histogram. |
| `fit` | `width,height` | Resize to cover this size, keeping the ratio, then crop the centre to exactly this size. The usual choice for square or fixed-size thumbnails. |
| `fliphoriz` | | Mirror left to right. |
| `flipvert` | | Mirror top to bottom. |
| `gblur` | `radius` | A Gaussian blur, up to `max_blur_radius`. |
| `grayscale` | | Convert to grey. |
| `invert` | | Make a negative. |
| `pad` | `width,height[,colour]` | Resize to fit inside this size, keeping the ratio, then pad to exactly this size with a hex colour (without `#`). Use 8 digits for transparency, e.g. `00000080`. The default is transparent if the image has transparency, otherwise white. |
| `posterize` | `bits` | Keep `1` to `8` bits per colour channel. |
| `resize` | `width,height` | Resize to exactly this size, stretching if the ratio differs. |
| `resizemax` | `width,height` | Resize to fit inside this size, keeping the ratio. |
| `resizemin` | `width,height` | Resize to cover this size, keeping the ratio. |
| `resizepc` | `x,y` | Resize by a fraction of the width and height, e.g. `0.5,0.5` for half. |
| `rotate` | `degrees[,colour]` | Rotate anticlockwise by a whole number of degrees. The image is enlarged to fit, so nothing is cut off. For angles that aren't a multiple of 90 this leaves corners, which are transparent, or filled with a hex colour (without `#`) if one is given, e.g. `rotate,15,ffffff`. |
| `rounded` | `radius` | Round the corners, making them transparent. `radius` is in pixels. |
| `sharpness` | `factor` | `1` leaves the image unchanged, higher is sharper. |
| `solarize` | `threshold` | Invert every value above the threshold, `0` to `255`. |
| `unsharp` | `[radius[,percent[,threshold]]]` | Sharpen with an unsharp mask, the usual way to sharpen after shrinking. `radius` is in pixels (default `2`, up to `max_blur_radius`), `percent` is the strength (default `150`) and `threshold` the smallest difference sharpened (default `3`). |

Transparency is kept by every operation except `grayscale` and `colorize`.
`circle`, `rounded`, `pad` and `rotate` can add transparency, so use PNG or
WebP output for them: JPEG flattens it onto white.

The sizes operations produce, and the radius of `gblur` and `unsharp`, are
[limited](configuration.md#limits).

## Output format

Use `format` to choose the format of the thumbnail. It can be `jpeg` (or
`jpg`), `png`, `gif`, `webp`, `bmp` or `tiff` (or `tif`), in any case. Any
other value is an error.

Without `format`, the thumbnail has the same format as the source. A source
in another format is returned as PNG, except MPO, which is returned as JPEG.
Only Safari displays TIFF, and BMP is saved uncompressed, so if your sources
might be either, give `format`.

Images with transparency are flattened onto a white background when saved
as JPEG, which has no transparency. Only the first frame of an animated
image is used, so thumbnails are never animated.

## EXIF orientation

Phones and cameras often store a photo sideways, with an EXIF tag saying how
to rotate it for display. Browsers follow the tag. With
`apply_exif_orientation` set to `True` (the default), the image is rotated
upright the same way before any operations run, so crop coordinates and
sizes refer to the image as it appears in a browser. Thumbnails are saved
without the tag, so browsers don't rotate them again.

Set it to `False` to process the pixels as stored.

## Speed

JPEGs, the usual format for large photos, can be decoded at 1/2, 1/4 or 1/8
of their size, which is several times faster and needs far less memory.
This happens automatically when the operations shrink the image anyway: e.g.
`fit,300,300` on a 6000 × 4000 photo takes about a quarter of the time and a
fifth of the memory. The result looks the same.

It only applies when the first operation that sets the size (`fit`, `pad`,
`resize`, `resizemax` or `resizemin`) comes before any that work in the
source's pixels, such as `resizepc`, `rotate`, `gblur` or `unsharp`. So put
the resize first where you can, e.g. `fit,300,300|gblur,2` rather than
`gblur,2|fit,300,300`. Crops and colour changes can go anywhere: a `crop`
box is given in the source's pixels, and is scaled to match, e.g.
`crop,0,0,4000,3000|resize,400,300` on a 6000 × 4000 photo decodes it at a
quarter of the size.
