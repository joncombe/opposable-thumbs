"""Every link in the documentation goes somewhere that exists."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# links to this repository on GitHub, as the README needs for PyPI
REPOSITORY = "https://github.com/joncombe/opposable-thumbs/blob/main/"
DOCUMENTS = [
    ROOT / "README.md",
    ROOT / "DEVELOP.md",
    ROOT / "CHANGELOG.md",
    *sorted((ROOT / "docs").glob("*.md")),
]

# skip the documents when run from an sdist, which has only some of them
pytestmark = pytest.mark.skipif(
    not (ROOT / "docs").exists(), reason="the docs aren't here"
)


def prose(path):
    # the text without code blocks or inline code, where links aren't links
    text = re.sub(r"^```.*?^```", "", path.read_text(), flags=re.M | re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def anchors(path):
    # GitHub's anchor for each heading: lower case, without punctuation, with
    # spaces as hyphens, and -1, -2... after repeats
    seen = {}
    result = set()
    text = re.sub(r"^```.*?^```", "", path.read_text(), flags=re.M | re.S)
    for heading in re.findall(r"^#+ (.+)$", text, flags=re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def links():
    return [
        pytest.param(document, target, id=f"{document.relative_to(ROOT)} -> {target}")
        for document in (DOCUMENTS if (ROOT / "docs").exists() else [])
        for target in re.findall(r"\]\(([^)\s]+)\)", prose(document))
    ]


@pytest.mark.parametrize("document, target", links())
def test_link(document, target):
    if target.startswith(REPOSITORY):
        path, _, anchor = target.removeprefix(REPOSITORY).partition("#")
        path = ROOT / path
    elif re.match(r"[a-z]+:", target):
        pytest.skip("an external link")
    else:
        path, _, anchor = target.partition("#")
        path = (document.parent / path).resolve() if path else document

    assert path.exists(), f"{path} doesn't exist"
    if anchor:
        assert anchor in anchors(path), f"{path.name} has no #{anchor}"


def test_readme_links_work_on_pypi():
    # PyPI shows only the README, so links to other files must be full URLs
    for target in re.findall(r"\]\(([^)\s]+)\)", prose(ROOT / "README.md")):
        assert re.match(r"(https?://|#)", target), target


def test_anchors(tmp_path):
    # the rules GitHub uses, so a broken link can't pass by accident
    page = tmp_path / "page.md"
    page.write_text(
        "# The Python API\n## make_thumbnail()\n## Using with Django\n"
        "## Notes\n## Notes\n```\n# not a heading\n```\n"
    )
    assert anchors(page) == {
        "the-python-api",
        "make_thumbnail",
        "using-with-django",
        "notes",
        "notes-1",
    }


# the docs match the code


def section(document, heading):
    """The text of a document from a heading to the next heading of the same
    or a higher level."""
    text = (ROOT / document).read_text()
    level = heading.split(" ")[0]
    start = text.index(f"\n{heading}\n")
    end = re.search(rf"\n#{{1,{len(level)}}} ", text[start + 1 :])
    return text[start : start + 1 + end.start()] if end else text[start:]


def table(text, header):
    """{first column: second column} of the table with this header row."""
    rows = text[text.index(header) :].split("\n\n")[0].splitlines()[2:]
    cells = [[c.strip() for c in row.strip("|").split(" | ")] for row in rows]
    return {c[0].strip("`"): c[1] if len(c) > 1 else "" for c in cells}


def test_settings_table():
    import dataclasses

    from opposable_thumbs import Config

    rows = table((ROOT / "docs/configuration.md").read_text(), "| Setting | Default |")
    fields = {f.name: f for f in dataclasses.fields(Config)}
    assert rows.keys() == fields.keys()
    for name, field in fields.items():
        default = (
            field.default_factory()
            if field.default is dataclasses.MISSING
            else field.default
        )
        if isinstance(default, str):
            shown = f'"{default}"'
        elif isinstance(default, tuple | dict):
            shown = repr(default).replace("'", '"')
        else:
            shown = repr(default)
        assert rows[name].startswith(f"`{shown}`"), (name, rows[name])


def test_limits_table():
    from opposable_thumbs import Config

    rows = table(section("docs/configuration.md", "## Limits"), "| Setting | Limits |")
    assert rows and all(hasattr(Config(), name) for name in rows)


def test_operations_table_and_playground():
    from opposable_thumbs.operations import OPERATIONS

    rows = table((ROOT / "docs/operations.md").read_text(), "| Operation |")
    assert rows.keys() == OPERATIONS.keys()
    playground = (ROOT / "playground/index.html").read_text()
    assert set(re.findall(r'^  \["(\w+)"', playground, re.M)) == OPERATIONS.keys()
    for document in ("README.md", "CHANGELOG.md"):
        count = re.search(r"(\d+) operations", (ROOT / document).read_text())
        assert int(count.group(1)) == len(OPERATIONS), document


def test_output_formats():
    from opposable_thumbs.imaging import FORMAT_ALIASES, OUTPUT_FORMATS

    text = section("docs/operations.md", "## Output format")
    first = text.split("\n\n")[1]
    named = {name.upper() for name in re.findall(r"`(\w+)`", first)} - {"FORMAT"}
    assert named == OUTPUT_FORMATS.keys() | FORMAT_ALIASES.keys()


@pytest.mark.parametrize("name", ["Result", "Thumbnail"])
def test_result_attributes(name):
    import dataclasses

    import opposable_thumbs

    cls = getattr(opposable_thumbs, name)
    rows = table(section("docs/python.md", f"## {name}"), "| Attribute |")
    properties = {n for n, v in vars(cls).items() if isinstance(v, property)}
    assert rows.keys() == {f.name for f in dataclasses.fields(cls)} | properties


def test_python_api():
    import inspect

    import opposable_thumbs

    text = (ROOT / "docs/python.md").read_text()
    for name in opposable_thumbs.__all__:
        assert f"## {name}" in text or f"`{name}`" in text, name

    arguments = table(section("docs/python.md", "## make_thumbnail()"), "| Argument |")
    parameters = inspect.signature(opposable_thumbs.make_thumbnail).parameters
    assert arguments.keys() == parameters.keys() - {"config"}


def test_error_statuses():
    import ast

    # the statuses written in calls to add_error() and SourceError(), and the
    # default. a status passed on from elsewhere (e.g. e.status) is counted
    # where it was written
    statuses = {400}
    for path in (ROOT / "src/opposable_thumbs").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                if name in ("add_error", "SourceError") and len(node.args) == 2:
                    if isinstance(node.args[1], ast.Constant):
                        statuses.add(node.args[1].value)

    rows = table(section("docs/python.md", "## Errors"), "| Status |")
    assert {int(status) for status in rows} == statuses


@pytest.mark.parametrize(
    "module, document",
    [
        ("opposable_thumbs.cli", "docs/caching.md"),
        (
            "opposable_thumbs.django.management.commands.clean_opposable_cache",
            "docs/django.md",
        ),
        ("opposable_thumbs.flask", "docs/flask.md"),
    ],
)
def test_command_options(module, document):
    import importlib
    import inspect

    source = inspect.getsource(importlib.import_module(module))
    options = set(re.findall(r'"(--[\w-]+)"', source))
    assert options
    text = (ROOT / document).read_text()
    assert {option for option in options if option not in text} == set()
