from setuptools import setup

setup(
    name="rubbish",
    version='0.1',
    py_modules=["rubbish"],
    install_requires=[
        'sqlalchemy', 'psycopg2', 'alembic', 'geoalchemy2', 'click'
    ],
    entry_points='''
        [console_scripts]
        rubbish-admin=rubbish:cli
    ''',
)
