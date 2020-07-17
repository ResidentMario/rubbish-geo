from setuptools import setup, find_packages

setup(
    name='rubbish_geo_client',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'shapely', 'geoalchemy2', 'scipy', 'click'
    ],
    extras_require={'develop': ['pylint', 'pytest', 'geopandas']},
)
