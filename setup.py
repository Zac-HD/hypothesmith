"""Packaging config for Hypothesmith."""

import os

import setuptools


def local_file(name: str) -> str:
    """Interpret filename as relative to this file."""
    return os.path.relpath(os.path.join(os.path.dirname(__file__), name))


SOURCE = local_file("src")
README = local_file("README.md")

with open(local_file("src/hypothesmith/__init__.py")) as o:
    for line in o:
        if line.startswith("__version__"):
            _, __version__, _ = line.split('"')


setuptools.setup(
    name="hypothesmith",
    version=__version__,
    author="Zac Hatfield-Dodds",
    author_email="zac@hypothesis.works",
    packages=setuptools.find_packages(SOURCE),
    package_dir={"": SOURCE},
    package_data={"": ["py.typed", "python.lark"]},
    url="https://github.com/Zac-HD/hypothesmith",
    project_urls={"Funding": "https://github.com/sponsors/Zac-HD"},
    license="MPL 2.0",
    description="Hypothesis strategies for generating Python programs, something like CSmith",
    zip_safe=False,
    install_requires=["hypothesis[lark]>=6.93.0", "libcst>=1.0.1"],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Framework :: Hypothesis",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Testing",
    ],
    long_description=open(README).read(),
    long_description_content_type="text/markdown",
    keywords="python testing fuzzing property-based-testing",
)
