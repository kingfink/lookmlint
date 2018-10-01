from setuptools import setup, find_packages

setup(
    name='lookmlint',
    version='0.1',
    install_requires=[
        'attrs',
        'click',
        'pyyaml',
    ],
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'lookmlint = lookmlint.cli:cli',
        ]
    },
)
