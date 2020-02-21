import datetime
import json
import shutil
from pathlib import Path

import click
import requests
from mutagen import File
from mutagen.flac import FLAC, Picture
from mutagen.id3 import PictureType
from mutagen.mp4 import MP4, AtomDataType, MP4Cover

VERSION = '0.1'

AUDIO_INFO_URL = 'https://api.bilibili.com/audio/music-service-c/songs/playing?song_id={}'
ALBUM_INFO_URL = 'https://api.bilibili.com/audio/music-service-c/menus/{}'


def get_json_from_respond(res):
    res_json = res.json()
    if res_json['msg'] != 'success':
        msg = f'''request error: remote respond {res_json['msg']}
        in request {res.url}
        {res_json}
        '''
        raise requests.exceptions.RequestException(msg)
    return res_json['data']


class Cache:
    def __init__(self):
        """一个缓存基类，能将远程的文件资料等缓存到本地。

        缓存机制一共有 3 级：

        - 运行时字典缓存
        - 本地文件缓存
        - 远端资源
        """
        self._cache = {}
        self.getters = [self._get_from_cache,
                        self._get_from_local, self._get_from_remote]

    def _get_from_cache(self, k):
        return self._cache.get(k)

    def _get_from_remote(self, k):
        raise NotImplementedError()

    def _get_from_local(self, k):
        raise NotImplementedError()

    def _put_to_cache(self, k, v):
        self._cache[k] = v

    def get(self, k, default=None):
        for getter in self.getters:
            v = getter(k)
            if v:
                return v
        return default


class CoverCache(Cache):
    def __init__(self, local_dir):
        super().__init__()
        local_dir = Path(local_dir)
        self.img_dir = local_dir / 'img'
        self.img_dir.mkdir(exist_ok=True)

    def _get_from_local(self, k):
        filename = Path(k).name
        img_path = self.img_dir / filename
        if not img_path.is_file():
            return None
        self._put_to_cache(k, img_path)
        return img_path

    def _get_from_remote(self, k):
        filename = Path(k).name
        img_path = self.img_dir / filename
        res = requests.get(k)
        with img_path.open('wb') as fp:
            fp.write(res.content)
        self._put_to_cache(k, img_path)
        return img_path


class JsonCache(Cache):
    JSON_URL = None
    JSON_DIR_NAME = None

    def __init__(self, local_dir):
        super().__init__()
        local_dir = Path(local_dir)
        self.json_dir = local_dir / self.JSON_DIR_NAME
        self.json_dir.mkdir(exist_ok=True)

    def _get_from_local(self, k):
        json_path = self.json_dir / f'{k}.json'
        if not json_path.exists():
            return None
        with json_path.open('r', encoding='utf-8') as fp:
            json_obj = json.load(fp)
        self._put_to_cache(k, json_obj)
        return json_obj

    def _get_from_remote(self, k):
        url = self.JSON_URL.format(k)
        res = requests.get(url)
        json_obj = get_json_from_respond(res)
        json_path = self.json_dir / f'{k}.json'
        with json_path.open('w', encoding='utf-8') as fp:
            json.dump(json_obj, fp,  ensure_ascii=False)
        self._put_to_cache(k, json_obj)
        return json_obj


class AlbumCache(JsonCache):
    JSON_URL = ALBUM_INFO_URL
    JSON_DIR_NAME = 'album'


class AudioCache(JsonCache):
    JSON_URL = AUDIO_INFO_URL
    JSON_DIR_NAME = 'audio'


ARTIST_SPLIT_SYMBOL = ' · '


def spilt_artist_str(s):
    return s.split(ARTIST_SPLIT_SYMBOL)


def format_artist_list(li):
    return '/'.join(li)


def get_year_from_timestamp(timestramp):
    return datetime.datetime.fromtimestamp(timestramp / 1000).year


class BilibiliMusicTagger:
    def __init__(self, album_cache, audio_cache, cover_cache, overwrite):
        self.album_cache = album_cache
        self.audio_cache = audio_cache
        self.cover_cache = cover_cache

        self.overwrite = overwrite

    def process_a_dir(self, input_dir, output_dir):
        for p in input_dir.iterdir():
            self.process_a_file(p, output_dir)

    def process_a_file(self, input_path, output_dir):
        au_id = input_path.name

        if not au_id.isdigit():
            print(f'unexpected file: {input_path}')
            return

        au_id = int(au_id)

        file_kind = File(input_path)

        if isinstance(file_kind, MP4):
            suffix = '.m4a'
        elif isinstance(file_kind, FLAC):
            suffix = '.flac'
        elif file_kind is None:
            raise TypeError('unknown file kind')
        else:
            raise TypeError(
                f'unsupport file kind {file_kind.__class__.__name__}')

        audio_info = self.audio_cache.get(au_id)
        filename = f'{spilt_artist_str(audio_info["author"])[0]} - {audio_info["title"]}{suffix}'

        output_path = output_dir / filename

        if not self.overwrite and output_path.is_file():
            print(f'{filename} exists, skipped')
            return

        print(f'processing: {filename}')

        shutil.copyfile(input_path, output_path)

        album_id = audio_info['pgc_info']['pgc_menu']['menuId']
        album_info = self.album_cache.get(album_id)
        album_cover_url = album_info['menusRespones']['coverUrl']

        album_au_ids = list(map(lambda x: x['id'], album_info['songsList']))
        track_id = album_au_ids.index(au_id)
        assert album_cover_url == album_info['songsList'][track_id]['cover_url']

        album_cover_path = self.cover_cache.get(album_cover_url)
        if album_cover_path.suffix == '.jpg':
            image_format = AtomDataType.JPEG
        elif album_cover_path.suffix == '.png':
            image_format = AtomDataType.PNG
        else:
            raise TypeError(
                f'Unsupport format: {album_cover_path.suffix}, Only support jpg and png.')

        with album_cover_path.open('rb') as fp:
            cover_image = fp.read()

        audio_file = File(output_path)

        if isinstance(audio_file, MP4):
            tags = {
                '\xa9nam': audio_info['title'],
                '\xa9alb': album_info['menusRespones']['title'],
                '\xa9ART': format_artist_list(spilt_artist_str(audio_info['author'])),
                '\xa9day': str(get_year_from_timestamp(album_info['menusRespones']['pbtime'])),
                'aART': format_artist_list(spilt_artist_str(album_info['menusRespones']['mbnames'])),
                'trkn': [(track_id + 1, album_info['menusRespones']['songNum'])],
                'disk': [(1, 1)],
                'covr': [MP4Cover(cover_image, imageformat=image_format)],
            }
        elif isinstance(audio_file, FLAC):
            tags = {
                'ALBUM': album_info['menusRespones']['title'],
                'ARTIST': format_artist_list(spilt_artist_str(audio_info['author'])),
                'ALBUMARTIST': format_artist_list(spilt_artist_str(album_info['menusRespones']['mbnames'])),
                'DATE': str(get_year_from_timestamp(album_info['menusRespones']['pbtime'])),
                'TITLE': audio_info['title'],
                'DISCNUMBER': '1',
                'DISCTOTAL': '1',
                'TRACKTOTAL': str(album_info['menusRespones']['songNum']),
                'TRACKNUMBER': str(track_id + 1),
            }

            picture = Picture()
            picture.data = cover_image
            picture.type = PictureType.COVER_FRONT

            audio_file.add_picture(picture)

        audio_file.update(tags)
        audio_file.save()


@click.command()
@click.argument('source', required=True, type=click.Path(exists=True))
@click.argument('output_dir', default=Path.cwd() / 'output', type=click.Path())
@click.option('--temp-dir', '-t', default=Path.cwd() / 'temp', show_default='./temp', type=click.Path(), help='temp directory, where some cache will put in.')
@click.option('--overwrite', is_flag=True, help='overwrite file if file exists.')
@click.version_option()
def cli(source, output_dir, temp_dir, overwrite):
    """A auto tagger for Bilibili music.

    SOURCE is a path to source directory or file.

    OUTPUT_DIR is output directory, [default: ./output]
    """
    source = Path(source)
    output_dir = Path(output_dir)
    temp_dir = Path(temp_dir)

    output_dir.mkdir(exist_ok=True)
    temp_dir.mkdir(exist_ok=True)

    album_cache = AlbumCache(temp_dir)
    audio_cache = AudioCache(temp_dir)
    cover_cache = CoverCache(temp_dir)

    tag_adder = BilibiliMusicTagger(
        album_cache, audio_cache, cover_cache, overwrite)

    if source.is_dir():
        tag_adder.process_a_dir(source, output_dir)
    else:
        tag_adder.process_a_file(source, output_dir)


if __name__ == "__main__":
    cli()
