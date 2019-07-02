import codecs
import os
import sys

from setuptools import find_packages, setup


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return codecs.open(file_path, encoding="utf-8").read()


with open("requirements.in") as f:
    install_requires = [line for line in f if line and line[0] not in "#-"]


if sys.version_info[0] == 2:
    install_requires.append("wrapt")

with open("test-requirements.in") as f:
    tests_require = [line for line in f if line and line[0] not in "#-"]

setup(
    name="konfetti",
    version="0.6.0",
    url="https://github.com/kiwicom/konfetti",
    license="MIT",
    author="Dmitry Dygalo",
    author_email="dmitry.dygalo@kiwi.com",
    description="`konfetti` provides a framework-independent way for "
    "configuration of applications or libraries written in Python.",
    long_description=read("README.rst"),
    long_description_content_type="text/x-rst",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*",
    install_requires=install_requires,
    extras_require={"vault": ["hvac", "tenacity"], "async-vault": ["aiohttp", "tenacity"]},
    tests_require=tests_require,
    include_package_data=True,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Environment :: Console",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: CPython",
        "License :: OSI Approved :: MIT License",
    ],
)
