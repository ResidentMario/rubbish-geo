from setuptools import setup, find_packages

setup(
    name='rubbish_geo_admin',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'sqlalchemy', 'psycopg2', 'geoalchemy2', 'click', 'osmnx', 'geopandas>=0.8.0', 'geopy',
        'rich', 'scipy'
    ],
    extras_require={'develop': [
        'alembic', 'pylint', 'pytest', 'functions-framework', 'firebase-admin',
        'google-cloud-logging'
    ]},
    entry_points='''
        [console_scripts]
        rubbish-admin=rubbish_geo_admin.cli:cli
    ''',
)
