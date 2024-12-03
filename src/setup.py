import json
import os
import re

from setuptools import find_packages, setup  # type: ignore

# Collect package metadata.

recipe = os.environ.get("RECIPE_DIR", "../recipe")
metasrc = os.path.join(recipe, "meta.json")
with open(metasrc, "r", encoding="utf-8") as f:
    meta = json.load(f)
name_conda = meta["name"]
name_py = name_conda.replace("-", "_")

# Define basic setup configuration.

kwargs = {
    "entry_points": {"console_scripts": ["wxvx = %s.cli:main" % name_py]},
    "include_package_data": True,
    "name": name_conda,
    "packages": find_packages(exclude=["%s.tests" % name_py], include=[name_py, "%s.*" % name_py]),
    "version": meta["version"],
}

# Define dependency packages for non-devshell installs.

if not os.environ.get("CONDEV_SHELL"):
    kwargs["install_requires"] = [
        pkg.replace(" =", "==")
        for pkg in meta["packages"]["run"]
        if not re.match(r"^python .*$", pkg)
    ]

# Install.

setup(**kwargs)
