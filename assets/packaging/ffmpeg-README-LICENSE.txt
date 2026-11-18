FFmpeg —— 第三方组件许可与源代码声明
======================================

本目录内的 ffmpeg.exe 和 ffprobe.exe 是 FFmpeg 项目的预编译可执行文件，取自 gyan.dev 发布的
“ffmpeg-release-essentials” 构建，采用 GNU General Public License v3 (GPLv3) 授权。
完整许可文本见同目录下的 COPYING.GPLv3.txt。

版权与来源
----------
- FFmpeg 版权归 FFmpeg 开发者及其贡献者所有。
- FFmpeg 官方主页：https://ffmpeg.org/
- FFmpeg 源代码：https://ffmpeg.org/download.html  以及  https://git.ffmpeg.org/ffmpeg.git
- 本 Windows 二进制及其构建脚本由 gyan.dev 发布：
    https://www.gyan.dev/ffmpeg/builds/
    构建脚本：https://github.com/GyanD/codexffmpeg

源代码提供声明（满足 GPLv3 第 6 条）
------------------------------------
与这两个可执行文件相对应的完整源代码，可从上述 FFmpeg 官方仓库与 gyan.dev 构建渠道
免费获取。如需协助获取对应版本源代码，可通过易声(EasyVoice) 项目仓库 issue 联系维护者。

易声(EasyVoice) 与 FFmpeg 的关系
--------------------------------
易声在音频转码、变速和视频导出时，以独立子进程调用 FFmpeg 工具。
这在 GPL 意义上属于“单纯聚合”
(mere aggregation)，因此 FFmpeg 的 GPLv3 不会传染到易声自身的代码；易声未修改 FFmpeg。
