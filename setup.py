from setuptools import setup, find_packages
import os.path
import unittest


def get_test_suite():
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('tests', pattern='test_*.py')
    return test_suite


this_directory = os.path.abspath(os.path.dirname(__file__))
readme_filename = os.path.join(this_directory, 'README.md')
with open(readme_filename, "r") as f:
    long_description = f.read()


setup(
    name="glib-log-bridge-Neui",
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
    ],
    python_requires='>=3.5',
    test_suite="setup.get_test_suite",
)
