from setuptools import setup, find_packages

setup(
    name='Run 6fdf8feb',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'fastapi',
        'uvicorn',
        'pydantic'
    ],
    python_requires='>=3.8',
)