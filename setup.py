from setuptools import setup, find_packages

setup(
    name="marsad-agents",
    version="1.0.0",
    author="AbuYahyaAlalwi2",
    description="Million-agent swarm with automatic signup and workflow",
    packages=find_packages(),
    install_requires=[
        "flask",
        "flask-cors",
        "requests",
        "gunicorn",
    ],
    entry_points={
        "console_scripts": [
            "marsad=marsad.cli:main",
        ],
    },
)
