from setuptools import setup, find_packages

setup(
    name='rubbish_geo_common',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'sqlalchemy', 'psycopg2', 'alembic', 'geoalchemy2'
    ],
)
