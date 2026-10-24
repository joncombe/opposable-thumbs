import os
import shutil
import time
from pathlib import Path

import pytest
from PIL import Image

from opposable_thumbs import Config, ConfigError, clean_cache, handle_request
from opposable_thumbs.cache import parse_size, write_cache_file

from helpers import FakeResponse, open_result, png_bytes


@pytest.fixture
def cached(images, tmp_path):
    return Config(
        signed_urls=False, roots={"images": images}, output_cache_dir=tmp_path / "out"
    )


def cache_files(config):
    return sorted(os.listdir(config.output_cache_dir))


def test_output_cache(thumb, cached):
    miss = thumb("rgb.png", "format=jpeg", config=cached)
    hit = thumb("rgb.png", "format=jpeg", config=cached)
    assert miss == hit
    assert hit.content_type == "image/jpeg"
    # no extension: the type is read from the file
    assert len(cache_files(cached)) == 1
    assert "." not in cache_files(cached)[0]


def test_cache_key_ignores_unknown_parameters(thumb, cached):
    thumb("rgb.png", "p=blur", config=cached)
    thumb("rgb.png", "p=blur&utm_source=x", config=cached)
    assert len(cache_files(cached)) == 1


def test_format_aliases_share_a_cache_entry(thumb, cached):
    thumb("rgb.png", "format=jpg", config=cached)
    thumb("rgb.png", "format=JPEG", config=cached)
    assert len(cache_files(cached)) == 1


@pytest.mark.parametrize(
    "query", ["p=blur", "format=png", "quality=50", "p=blur&format=webp"]
)
def test_cache_key_includes_what_changes_the_output(thumb, cached, query):
    thumb("rgb.png", config=cached)
    thumb("rgb.png", query, config=cached)
    assert len(cache_files(cached)) == 2


def test_cache_key_includes_exif_setting(thumb, cached, images):
    other = Config(
        signed_urls=False,
        roots={"images": images},
        output_cache_dir=cached.output_cache_dir,
        apply_exif_orientation=False,
    )
    upright = thumb("sideways.jpg", config=cached)
    stored = thumb("sideways.jpg", config=other)
    assert open_result(upright).size != open_result(stored).size


def test_unreadable_cache_file_is_replaced(thumb, cached):
    thumb("rgb.png", config=cached)
    path = os.path.join(cached.output_cache_dir, cache_files(cached)[0])
    with open(path, "wb") as f:
        f.write(b"junk")

    result = thumb("rgb.png", config=cached)
    assert open_result(result).format == "PNG"
    assert Path(path).read_bytes() == result.body


def test_expired_cache_file_is_replaced(thumb, images, tmp_path):
    config = Config(
        signed_urls=False,
        roots={"images": images},
        output_cache_dir=tmp_path / "out",
        cache_max_age=60,
    )
    thumb("rgb.png", config=config)
    path = os.path.join(config.output_cache_dir, cache_files(config)[0])
    os.utime(path, (time.time() - 120,) * 2)

    thumb("rgb.png", config=config)
    assert time.time() - os.path.getmtime(path) < 60


def test_disallowed_source_is_not_served_from_cache(thumb, cached):
    assert thumb("rgb.png", config=cached).status == 200
    assert (
        thumb(
            "rgb.png",
            config=Config(signed_urls=False, output_cache_dir=cached.output_cache_dir),
        ).status
        == 403
    )


def test_cache_folder_is_recreated(thumb, cached):
    thumb("rgb.png", config=cached)
    shutil.rmtree(cached.output_cache_dir)
    thumb("rgb.png", "p=blur", config=cached)
    assert len(cache_files(cached)) == 1


def test_write_cache_file_leaves_no_temp_file(tmp_path):
    write_cache_file(str(tmp_path / "a" / "b"), b"data")
    assert os.listdir(tmp_path / "a") == ["b"]


def test_input_cache(fake_fetch, tmp_path):
    fake_fetch.response = FakeResponse(png_bytes())
    config = Config(
        signed_urls=False,
        allowed_urls=["https://example.com/"],
        input_cache_dir=tmp_path / "in",
    )
    for p in ("blur", "invert"):
        result = handle_request(config, f"url=https://example.com/a.png&p={p}")
        assert result.status == 200

    assert len(fake_fetch.calls) == 1
    assert len(os.listdir(tmp_path / "in")) == 1


def test_failed_fetch_does_not_use_expired_input(fake_fetch, tmp_path):
    fake_fetch.response = FakeResponse(png_bytes())
    config = Config(
        signed_urls=False,
        allowed_urls=["https://example.com/"],
        input_cache_dir=tmp_path / "in",
        cache_max_age=60,
    )
    query = "url=https://example.com/a.png"
    handle_request(config, query)
    path = tmp_path / "in" / os.listdir(tmp_path / "in")[0]
    os.utime(path, (time.time() - 120,) * 2)

    fake_fetch.response = FakeResponse(status_code=500)
    assert handle_request(config, query).status == 502


# clean_cache


@pytest.fixture
def cache_dirs(tmp_path):
    config = Config(
        signed_urls=False,
        input_cache_dir=tmp_path / "in",
        output_cache_dir=tmp_path / "out",
        cache_max_age=60,
    )
    old = time.time() - 120
    for folder in (config.input_cache_dir, config.output_cache_dir):
        os.makedirs(folder)
        for name in ("a" * 32, "b" * 32, f"{'c' * 32}.{'d' * 32}.tmp", "keep.txt"):
            path = os.path.join(folder, name)
            Image.new("RGB", (1, 1)).save(path, "PNG")
            if name != "b" * 32:
                os.utime(path, (old, old))
    return config


def test_clean_cache_deletes_expired_files(cache_dirs):
    assert clean_cache(cache_dirs) == 4
    for folder in (cache_dirs.input_cache_dir, cache_dirs.output_cache_dir):
        assert sorted(os.listdir(folder)) == ["b" * 32, "keep.txt"]


def test_clean_cache_all(cache_dirs):
    assert clean_cache(cache_dirs, all=True) == 6
    for folder in (cache_dirs.input_cache_dir, cache_dirs.output_cache_dir):
        assert os.listdir(folder) == ["keep.txt"]


def test_clean_cache_without_max_age(tmp_path):
    config = Config(signed_urls=False, output_cache_dir=tmp_path, cache_max_age=None)
    (tmp_path / ("a" * 32)).write_bytes(b"")
    assert clean_cache(config) == 0
    assert clean_cache(config, all=True) == 1


def test_clean_cache_missing_folders():
    assert (
        clean_cache(Config(signed_urls=False, output_cache_dir="/nonexistent/folder"))
        == 0
    )


def test_changed_source_file_gets_a_new_thumbnail(images, cached, thumb):
    Image.new("RGB", (40, 30), "red").save(images / "changing.png")
    first = thumb("changing.png", config=cached)
    Image.new("RGB", (40, 30), "blue").save(images / "changing.png")
    os.utime(images / "changing.png", ns=(1, 1))
    second = thumb("changing.png", config=cached)
    assert first.body != second.body


def test_unwritable_output_cache_still_returns_the_image(
    images, thumb, tmp_path, caplog
):
    # a cache folder inside a file can never be created
    (tmp_path / "file").write_bytes(b"")
    config = Config(
        signed_urls=False,
        roots={"images": images},
        output_cache_dir=tmp_path / "file" / "c",
    )
    assert thumb("rgb.png", config=config).status == 200
    assert "Can't write cache file" in caplog.text


def test_changing_the_url_downloads_it_again(fake_fetch, tmp_path):
    # the documented way to refresh a url source that changed online
    fake_fetch.response = FakeResponse(png_bytes())
    config = Config(
        signed_urls=False,
        allowed_urls=["https://example.com/"],
        input_cache_dir=tmp_path / "in",
        output_cache_dir=tmp_path / "out",
    )
    for query in ("url=https://example.com/a.png", "url=https://example.com/a.png?v=2"):
        assert handle_request(config, query).status == 200
    assert len(fake_fetch.calls) == 2


# size limit


@pytest.mark.parametrize(
    "size, expected",
    [
        (None, None),
        (0, 0),
        (1234, 1234),
        ("1234", 1234),
        ("500KB", 500_000),
        ("500 mb", 500_000_000),
        ("5G", 5_000_000_000),
        ("1.5GB", 1_500_000_000),
        ("2TB", 2_000_000_000_000),
    ],
)
def test_parse_size(size, expected):
    assert parse_size(size) == expected


@pytest.mark.parametrize("size", ["", "lots", "5XB", "-1", -1, True, [5]])
def test_parse_invalid_size(size):
    with pytest.raises(ValueError, match="Invalid size"):
        parse_size(size)


def test_cache_max_size_setting():
    assert Config(cache_max_size="5GB").cache_max_size == 5_000_000_000
    with pytest.raises(ConfigError, match="cache_max_size"):
        Config(cache_max_size="lots")


@pytest.fixture
def sized(tmp_path):
    """Two cache folders, each with four 100-byte files written 1 to 4 hours
    ago (a is oldest), and a file being written."""
    config = Config(
        input_cache_dir=tmp_path / "in",
        output_cache_dir=tmp_path / "out",
        cache_max_size=250,
    )
    for folder in (config.input_cache_dir, config.output_cache_dir):
        os.makedirs(folder)
        for hours, letter in enumerate("dcba", start=1):
            path = os.path.join(folder, letter * 32)
            Path(path).write_bytes(b"x" * 100)
            os.utime(path, (time.time() - hours * 3600,) * 2)
        Path(folder, f"{'e' * 32}.{'f' * 32}.tmp").write_bytes(b"x" * 10)
    return config


def remaining(folder):
    return sorted(name[0] for name in os.listdir(folder))


def test_size_limit_deletes_the_oldest(sized):
    # 410 bytes in each folder: deleting a and b leaves 210
    assert clean_cache(sized) == 4
    for folder in (sized.input_cache_dir, sized.output_cache_dir):
        assert remaining(folder) == ["c", "d", "e"]


def test_size_limit_argument(sized):
    assert clean_cache(sized, max_size="1KB") == 0
    assert clean_cache(sized, max_size=0) == 8
    # files still being written are left alone
    assert remaining(sized.output_cache_dir) == ["e"]


def test_expired_files_go_first(sized):
    config = Config(
        output_cache_dir=sized.output_cache_dir,
        cache_max_age=2.5 * 3600,
        cache_max_size=150,
    )
    # a and b have expired, which leaves 210 bytes, so c goes too
    assert clean_cache(config) == 3
    assert remaining(sized.output_cache_dir) == ["d", "e"]


def test_no_size_limit(sized):
    config = Config(output_cache_dir=sized.output_cache_dir, cache_max_age=None)
    assert clean_cache(config) == 0
