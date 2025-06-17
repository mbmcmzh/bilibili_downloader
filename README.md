# B站视频下载器 (Bilibili Video Downloader)

一个功能强大的B站视频下载工具，支持多种清晰度和分P视频下载。

main分支为课程作业（）

## 功能特点

- 🎥 支持多种输入格式：av号、BV号、完整视频链接
- 📺 支持多种清晰度：从360P到4K超清
- 📑 支持分P视频：可选择下载全部或指定分P
- 🔄 智能下载：自动尝试DASH格式，回退到传统格式
- 🎵 音视频合并：支持ffmpeg和moviepy两种合并方式
- 📊 实时进度显示：下载进度和速度实时显示
- 🛡️ 错误处理：完善的异常处理和重试机制

## 支持的清晰度

| 代码 | 清晰度 | 说明 |
|------|--------|------|
| 120 | 超清4K | 需要大会员 |
| 116 | 高清1080P60 | 需要大会员 |
| 112 | 高清1080P+ | 需要大会员 |
| 80 | 高清1080P | 推荐 |
| 74 | 高清720P60 | 需要大会员 |
| 64 | 高清720P | |
| 32 | 清晰480P | |
| 16 | 流畅360P | |

## 安装要求

- Python 3.11+
- 依赖包：requests, moviepy
- 可选：ffmpeg (推荐安装以获得更好的合并性能)

## 安装方法

### 使用 uv (推荐)

```bash
# 克隆项目
git clone https://github.com/mbmcmzh/bilibili_downloader.git
cd bilibili_downloader

# 安装依赖
uv sync
```

### 使用 pip

```bash
# 克隆项目
git clone https://github.com/mbmcmzh/bilibili_downloader.git
cd bilibili_downloader

# 安装依赖
pip install -r requirements.txt
```

## 使用方法

### 命令行使用

```bash
python bili_download.py
```

然后按照提示输入：
1. 视频链接、av号或BV号
2. 选择清晰度
3. 选择下载全部分P或指定分P

### 支持的输入格式

- **完整链接**: `https://www.bilibili.com/video/BV1xx411c7mD`
- **BV号**: `BV1xx411c7mD`
- **av号**: `123456789`
- **带分P的链接**: `https://www.bilibili.com/video/BV1xx411c7mD?p=2`

### 程序化使用

```python
from bili_download import BilibiliDownloader

# 创建下载器实例
downloader = BilibiliDownloader()

# 下载视频 (默认1080P)
downloader.download("BV1xx411c7mD")

# 指定清晰度下载
downloader.download("BV1xx411c7mD", quality=120)

# 下载指定分P
downloader.download("BV1xx411c7mD", quality=80, target_page=2)
```

## 配置说明

### SESSDATA配置

为了下载高清晰度视频，您需要配置B站的SESSDATA：

1. 登录B站网页版
2. 打开浏览器开发者工具 (F12)
3. 在Application/Storage -> Cookies中找到SESSDATA
4. 复制SESSDATA值并替换代码中的默认值

```python
downloader = BilibiliDownloader(sessdata="your_sessdata_here")
```

## 文件结构

```
bilibili_downloader/
├── bili_download.py      # 主程序文件
├── bili_download/        # 下载文件存放目录
├── pyproject.toml        # 项目配置文件
├── uv.lock              # 依赖锁定文件
├── .gitignore           # Git忽略文件
├── README.md            # 项目说明文档
└── 流程图.png           # 程序流程图
```

## 注意事项

1. **版权声明**: 请仅下载您有权下载的内容，尊重版权
2. **网络环境**: 建议在良好的网络环境下使用
3. **存储空间**: 确保有足够的磁盘空间存储下载的视频
4. **ffmpeg**: 安装ffmpeg可以获得更好的音视频合并性能

## 常见问题

### Q: 下载失败怎么办？
A: 检查网络连接，确认视频链接有效，尝试更新SESSDATA

### Q: 无法下载高清晰度视频？
A: 需要B站大会员账号并正确配置SESSDATA

### Q: 音视频合并失败？
A: 安装ffmpeg或确保moviepy正常工作

## 贡献

欢迎提交Issue和Pull Request来改进这个项目！

## 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 免责声明

本工具仅供学习和研究使用，请遵守相关法律法规和平台服务条款。使用本工具下载的内容，请确保您拥有相应的权利或已获得授权。作者不承担因使用本工具而产生的任何法律责任。
