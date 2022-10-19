from setuptools import setup

with open("README.md", "rt", encoding="utf8") as f:
    README = f.read()

setup(
    name="KOMOE",
    version="0.1.0",
    description="A static site generator",
    long_description=README,
    long_description_content_type="text/markdown",
    license="MIT License",
    author="Louis DEVIE",
    url="https://github.com/louisdevie/komoe",
    packages=["komoe"],
    classifiers=[
        "Development Status :: 1 - Planning",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
    ],
    keywords=[
        "static",
        "site",
        "website",
        "template",
        "templating",
    ],
    python_requires=">=3.10",
    install_requires=[
        "Jinja2>=3.1.2",
        "Markdown==3.4.1",
        "click>=8.1.3",
        "tomli>=2.0.1",
    ],
    entry_points={
        "console_scripts": [
            "komoe = komoe.commands:main",
        ]
    },
)
