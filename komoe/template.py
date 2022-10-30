import os

CONFIG = """\
# Configuration for KOMOE static site generator.

komoe_require = '0.3'

[project]
name = '{0}'

[build]
source = 'source'
templates = 'templates'
static = 'static'
output = 'build'
"""

BASE = """\
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ TITLE }}</title>
</head>
<body>
    {{ CONTENT }}
</body>
</html>
"""

PAGE = """\
@base

# {0}

Welcome to the Komoe quickstart !
"""


def create_new_project(path, name):
    with open(path / "komoe.toml", "wt+", encoding="utf8") as f:
        f.write(CONFIG.format(name))

    os.mkdir(path / "source")

    with open(path / "source" / "index.md", "wt+", encoding="utf8") as f:
        f.write(PAGE.format(name))

    os.mkdir(path / "templates")

    with open(path / "templates" / "base.j2.html", "wt+", encoding="utf8") as f:
        f.write(BASE)

    os.mkdir(path / "static")
