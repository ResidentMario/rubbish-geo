from setuptools import setup, find_packages

setup(
    name='rubbish_geo_client',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'sqlalchemy', 'psycopg2', 'geoalchemy2', 'click', 'osmnx', 'geopandas', 'geopy',
        'rich', 'scipy'
    ],
    extras_require={'develop': ['pylint', 'pytest']},
)
