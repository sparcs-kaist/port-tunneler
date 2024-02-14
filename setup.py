import setuptools
import re

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("ptunnel/__main__.py", "r") as fh:
    version = re.search(r'__version__ = "(.*)"', fh.read()).group(1)

with open("requirements.txt", "r") as fh:
    install_requires = fh.read().splitlines()

setuptools.setup(
    name="sparcs-ptunnel",
    version=version,
    author="Roul",
    author_email="roul@sparcs.org",
    description="Simple port forwarding tool for SPARCS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8.0",
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "ptunnel = ptunnel.__main__:main",
        ]
    },
)
