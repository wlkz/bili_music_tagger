import datetime
import json
import shutil
from pathlib import Path

import click
import requests
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


class AlbumCache(Cache):
    def __init__(self, local_dir):
        super().__init__()
        local_dir = Path(local_dir)
        self.info_dir = local_dir / 'info'
        self.info_dir.mkdir(exist_ok=True)

    def _get_from_local(self, k):
        info_path = self.info_dir / f'{k}.json'
        if not info_path.exists():
            return None
        with info_path.open('r', encoding='utf-8') as fp:
            info = json.load(fp)
        self._put_to_cache(k, info)
        return info

    def _get_from_remote(self, k):
        url = ALBUM_INFO_URL.format(k)
        res = requests.get(url)
        album_info = get_json_from_respond(res)
        info_path = self.info_dir / f'{k}.json'
        with info_path.open('w', encoding='utf-8') as fp:
            json.dump(album_info, fp)
        self._put_to_cache(k, album_info)
        return album_info


def get_audio_info(au_id):
    res = requests.get(AUDIO_INFO_URL.format(au_id))
    return get_json_from_respond(res)


ARTIST_SPLIT_SYMBOL = ' · '


def spilt_artist_str(s):
    return s.split(ARTIST_SPLIT_SYMBOL)


class BilibiliMusicTagger:
    def __init__(self, album_cache, cover_cache):
        self.album_cache = album_cache
        self.cover_cache = cover_cache

    def process_a_dir(self, input_dir, output_dir):
        for p in input_dir.iterdir():
            self.process_a_file(p, output_dir)

    def process_a_file(self, input_path, output_dir):
        au_id = int(input_path.stem)
        audio_info = get_audio_info(au_id)

        filename = f'{spilt_artist_str(audio_info["author"])[0]} - {audio_info["title"]}.m4a'

        print(f'processing: {filename}')

        output_path = output_dir / filename
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

        tags = {
            '\xa9nam': audio_info['title'],
            '\xa9alb': album_info['menusRespones']['title'],
            '\xa9ART': '/'.join(spilt_artist_str(audio_info['author'])),
            '\xa9day': str(datetime.datetime.fromtimestamp(album_info['menusRespones']['pbtime'] / 1000).year),
            'aART': '/'.join(spilt_artist_str(album_info['menusRespones']['mbnames'])),
            'trkn': [(track_id + 1, album_info['menusRespones']['songNum'])],
            'disk': [(1, 1)],
            'covr': [MP4Cover(cover_image, imageformat=image_format)],
        }

        m4a_file = MP4(output_path)
        m4a_file.update(tags)
        m4a_file.save()


@click.command()
@click.argument('source', required=True, type=click.Path(exists=True))
@click.argument('output_dir', default=Path.cwd() / 'output', type=click.Path())
@click.option('--temp-dir', '-t', default=Path.cwd() / 'temp', show_default='./temp', type=click.Path(), help='temp directory, where some cache will put in.')
@click.version_option()
def cli(source, output_dir, temp_dir):
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
    cover_cache = CoverCache(temp_dir)

    tag_adder = BilibiliMusicTagger(album_cache, cover_cache)

    if source.is_dir():
        tag_adder.process_a_dir(source, output_dir)
    else:
        tag_adder.process_a_file(source, output_dir)


if __name__ == "__main__":
    cli()
