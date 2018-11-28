from setuptools import setup, find_packages

with open('readme.md') as f:
    long_description = f.read()

setup(
    name='lookmlint',
    description='Linter for LookML',
    version='0.1.0',
    author='Ryan Tuck',
    author_email='ryan.tuck@warbyparker.com',
    url='https://github.com/WarbyParker/lookmlint',
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=[
        'attrs',
        'click',
        'pyyaml',
    ],
    packages=['lookmlint'],
    entry_points={
        'console_scripts': [
            'lookmlint = lookmlint.cli:cli',
        ]
    },
)
