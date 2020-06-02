from setuptools import setup, find_packages

setup(
    name="rubbish",
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'sqlalchemy', 'psycopg2', 'alembic', 'geoalchemy2', 'click', 'osmnx', 'geopandas'
    ],
    extras_require={'develop': ['pylint', 'pytest']},
    entry_points='''
        [console_scripts]
        rubbish-admin=rubbish.admin.rubbish:cli
    ''',
)
