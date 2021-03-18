from setuptools import setup, find_packages
import os.path
import unittest


this_directory = os.path.abspath(os.path.dirname(__file__))
readme_filename = os.path.join(this_directory, 'README.md')
with open(readme_filename, "r") as f:
    long_description = f.read()


setup(
    name="glib-log-bridge",
    version="0.0.1",
    author="Neui",
    # author_email="author@example.com",
    description="Bridge Python and GLib logging facilities",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Neui/python-glib-log-bridge",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Topic :: System :: Logging",
        "Typing :: Typed",
    ],
    python_requires='>=3.5',
    test_suite="tests",
)
