from setuptools import setup

from bili_music_tagger import VERSION

setup(
    name='bili_music_tagger',
    version=VERSION,
    author="wlkz",
    py_modules=['bili_music_tagger'],
    description="A auto tagger for Bilibili music",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wlkz/bili_music_tagger",
    install_requires=[
        'click',
        'requests',
        'mutagen',
    ],
    entry_points='''
        [console_scripts]
        bili-music-tagger=bili_music_tagger:cli
    ''',
)