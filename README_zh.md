# bili_music_tagger

一个能自动将 Bilibili 音频上缓存的音乐自动添加元数据（歌曲名称、歌手等）信息的小脚本。

![before](docs/before.png)

![after](docs/after.png)

## 动机

Bilibili 音频缓存的文件（以 android 为例）在 `/sdcard/android/data/tv.danmaku.bili/files/audio_music` 里。里面文件为 AU ID 命名的文件。

这些文件的封装格式有两种，一种是使用 `flac` 封装的无损音乐，非无损音乐是使用 `mp4` 封装的 `aac` 音乐。我们可以直接添加文件后缀 ，即可在大多数播放器播放。

然而这些文件并没有像网易云音乐一样自动帮我们添加好标签和封面。这个脚本能自动判断音乐格式，从 Bilibili 上获取歌曲信息，自动填写歌曲元数据，并将歌曲名称命名为 `{第一位艺术家} - {标题}.{对应后缀}` 。

![tag_simple](docs/tag_simple.png)

目前支持以下信息的自动填写：

- 艺术家
- 标题
- 专辑
- 日期
- 专辑歌手
- 音轨号
- 合计音轨
- 专辑封面

## 使用方法

### 准备

[下载源码](https://github.com/wlkz/bili_music_tagger/archive/master.zip)（或者 `git clone` ）。

这个脚本由 Python 编写，需要安装 Python 3.7 以上的版本。可以到 [官网](https://www.python.org/downloads/) 下载最新的 Python。

这里有个[教程](https://www.liaoxuefeng.com/wiki/1016959663602400/1016959856222624)，可以作参考。注意，安装过程中，务必勾上 `Add Python 3.8 to PATH` 选项。

#### 用 PIP 安装（推荐）

以下均以 Windows 环境为例。

在源码目录里（如果你是用下载压缩包形式下载的，请解压），按住 `Shift` 键在空白处右键，选择 `在此处打开 Powershell 窗口` （Win7 为 打开cmd 窗口）。

在新开出来的命令行窗口，输入以下命令。

```sh
pip install -e .
```

完成安装。

#### 直接运行（不推荐）

适合有经验的 Python 使用者。

请自行安装以下依赖。

```text
requests
click
mutagen
```

请使用命令 `python bili_music_tagger.py` 代替 `bili-music-tagger` 即可。

如果不知道上面是啥意思，请不要使用这一方式运行。

### 快速开始

```text
Usage: bili-music-tagger [OPTIONS] SOURCE [OUTPUT_DIR]

  SOURCE 是待转换文件或者目录的路径.

  OUTPUT_DIR 是输出路径, [默认: ./output]

Options:
  -t, --temp-dir PATH  临时目录，存放各种缓存。
  --version            显示版本号。
  --help               显示帮助。
```

大多数情况下，可以新建一个目录，以 `./source` 为例。将 `/sdcard/android/data/tv.danmaku.bili/files/audio_music` 里文件全部拷贝进去。运行以下命令。

```sh
bili-music-tagger ./source
```

输出默认将在 `./output` 下。

## 常见问题

### 为啥不能运行

请确保你安装好环境，输入的命令准确无误。

如果确定没有问题，请继续阅读。

### 出现形如 `Traceback (most recent call last):` 的输出

请发 [Issue](https://github.com/wlkz/bili_music_tagger/issues) ，描述你遇到的问题，并附上你的输出。

现在已知：

- 当歌曲已经被已被下架，会输出以下信息
  
  ```text
  requests.exceptions.RequestException: request error: remote respond 该音频不存在或已被下架
        in request https://api.bilibili.com/audio/music-service-c/songs/playing?song_id=192306
        {'code': 7201006, 'msg': '该音频不存在或已被下架', 'data': None}
  ```

  这时请将此文件移除出输出目录即可。

  UPD:

  现在，音频文件信息也会进行缓存，这样大概能规避掉以前能生成，下架后无法生成的尴尬情况。

### 歌曲出现多演唱者的处理逻辑

根据小范围的观察，Bilibili 音频貌似使用了 `·` 作为分隔符，目前暂时会将该分隔符改为 `/` 。

[相关逻辑](https://github.com/wlkz/bili_music_tagger/blob/master/bili_music_tagger.py#L121-L122)

在这一个版本上暂时不会做大改。待收集更多资料后再做改动。

<!-- 真的有包含  `·` 的歌手吗？  -->

### 想要新的功能

- 输出文件格式自定义
  
  暂时不想动，有好的想法可以发 issue 。

- 下载歌曲
  
  不考虑，客户端下载感觉已经足够了，不值得再去重复写了。

  真想要请 PR 。

- 其他功能

  请发 [Issue](https://github.com/wlkz/bili_music_tagger/issues) 。

## 更新日志

### 0.1

#### 2020 年 2 月 21 日

- 增加对缓存的无损音乐的支持
- 音频文件信息也会进行缓存
- 忽略掉非缓存（即文件名不是全数字组成）的文件

#### 2020 年 2 月 1 日

- 完成基本功能

## 感谢

[@haozi23333](https://github.com/haozi23333) 提供的 Bilibili 音频的 API。原文：[https://haozi.moe/2019/11/02/bilibili-audio-api/](https://haozi.moe/2019/11/02/bilibili-audio-api/)

## 许可证

MIT License
