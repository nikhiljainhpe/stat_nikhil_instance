from setuptools import setup, find_packages

setup(
    name='StatHPCM_DBPlugin',
    version='1.0',
    packages=['stathpcmdbplugin'],
    entry_points={
        'trac.plugins': [
            'stathpcmdbplugin = stathpcmdbplugin'
        ]
    }
)


