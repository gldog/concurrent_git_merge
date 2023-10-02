import os

from setuptools import setup
from src.merge_git_repos import __version__

lib_folder = os.path.dirname(os.path.realpath(__file__))
requirement_path = f"{lib_folder}/requirements.txt"
install_requires = []
if os.path.isfile(requirement_path):
    with open(requirement_path) as f:
        install_requires = f.read().splitlines()

setup(
    name='src',
    version=__version__,
    description='',
    packages=['src'],
    install_requires=install_requires,
    entry_points={
        'console_scripts': ['src=src.merge_git_repos:main'],
    },
)
