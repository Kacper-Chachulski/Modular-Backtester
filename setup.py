from pathlib import Path

from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

ROOT = Path(__file__).parent

setup(
    ext_modules=[
        Pybind11Extension(
            "backtester._native",
            [str(ROOT / "cpp" / "engine.cpp")],
            cxx_std=17,
        )
    ],
    cmdclass={"build_ext": build_ext},
)
