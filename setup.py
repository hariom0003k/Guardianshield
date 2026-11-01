"""
Setup configuration for Guardian Shield.
"""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="guardian-shield",
    version="2.0.0",
    author="Guardian Shield Contributors",
    description="Enterprise-Grade Shoulder-Surfing Detection & Active Privacy Protection",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/guardian-shield",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Security",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "guardian-shield=main:main",
        ],
    },
)
