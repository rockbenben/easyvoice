FFmpeg —— 第三方组件许可与源代码声明
======================================

本目录内的 ffmpeg.exe 是 FFmpeg 项目的预编译可执行文件，取自 gyan.dev 发布的
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
与本 ffmpeg.exe 相对应的完整源代码，可从上述 FFmpeg 官方仓库与 gyan.dev 构建渠道
免费获取。如需协助获取对应版本源代码，可通过易声(EasyVoice) 项目仓库 issue 联系维护者。

易声(EasyVoice) 与 FFmpeg 的关系
--------------------------------
易声仅在“变速（语速 ≠ 1.0）”功能中，以【独立子进程】方式调用 ffmpeg.exe
（Python subprocess 调用，并非与之链接）。这在 GPL 意义上属于“单纯聚合”
(mere aggregation)，因此 FFmpeg 的 GPLv3 不会传染到易声自身的代码；易声未修改 FFmpeg。
若缺少本 ffmpeg.exe，易声会自动优雅降级（变速功能不生效，其余功能照常）。
