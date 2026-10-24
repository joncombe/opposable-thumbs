import os
import time
from pathlib import Path

import pytest

from opposable_thumbs.cli import main


def make_cache_file(folder, age):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "a" * 32)
    open(path, "wb").close()
    os.utime(path, (time.time() - age,) * 2)
    return path


def test_clean_cache(tmp_path, capsys):
    old = make_cache_file(tmp_path / "out", age=120)
    main(
        ["clean-cache", "--output-cache-dir", str(tmp_path / "out"), "--max-age", "60"]
    )
    assert not os.path.exists(old)
    assert capsys.readouterr().out == "Deleted 1 cached file(s)\n"


def test_clean_cache_keeps_fresh_files(tmp_path, capsys):
    fresh = make_cache_file(tmp_path / "in", age=0)
    main(["clean-cache", "--input-cache-dir", str(tmp_path / "in")])
    assert os.path.exists(fresh)


def test_clean_cache_all(tmp_path, capsys):
    fresh = make_cache_file(tmp_path / "in", age=0)
    main(["clean-cache", "--input-cache-dir", str(tmp_path / "in"), "--all"])
    assert not os.path.exists(fresh)


def test_clean_cache_needs_a_folder(capsys):
    with pytest.raises(SystemExit):
        main(["clean-cache"])
    assert "give --input-cache-dir" in capsys.readouterr().err


def test_clean_cache_max_size(tmp_path, capsys):
    folder = tmp_path / "out"
    old = make_cache_file(folder, age=60)
    Path(old).write_bytes(b"x" * 100)
    os.utime(old, (time.time() - 60,) * 2)
    main(["clean-cache", "--output-cache-dir", str(folder), "--max-size", "50"])
    assert not os.path.exists(old)
    assert capsys.readouterr().out == "Deleted 1 cached file(s)\n"


def test_clean_cache_invalid_max_size(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["clean-cache", "--output-cache-dir", str(tmp_path), "--max-size", "x"])
    assert "Invalid size" in capsys.readouterr().err
