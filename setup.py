from setuptools import setup

setup(
    name="data_lunch_cli",
    version="1.7.2",
    py_modules=["data_lunch_app"],
    install_requires=[
        "sqlalchemy==1.4.39",
        "hydra-core==1.1.1",
    ],
    entry_points={
        "console_scripts": [
            "data-lunch = data_lunch_app.cli:main",
        ],
    },
)
