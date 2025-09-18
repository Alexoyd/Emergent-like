from setuptools import setup, find_packages

setup(
    name='Run 24e4f92a',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'fastapi',
        'uvicorn',
        'pydantic'
    ],
    python_requires='>=3.8',
)