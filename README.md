# Video2URL4VRC

VRCHAT 视频流服务器 - 上传视频并生成可分享的流媒体链接，用于 VRCHAT 中的 VideoPlayer 组件。

## 功能特点

- 🌐 Web 界面上传（支持拖拽）
- ⚡ 自动转码为 H.264/AAC MP4 格式（VRCHAT 最佳兼容性）
- 📹 高质量输出（CRF 18, 192kbps AAC, 48kHz 立体声）
- 🔗 生成可分享的流媒体链接
- 📁 文件夹管理与视频整理
- 📊 实时上传与转码进度

## 目录结构

```
项目代码 (/root/projects/)
├── app.py              # Flask 主应用
├── upload.py           # CLI 上传工具
├── templates/          # Web 前端模板
│   └── index.html      # 上传界面
├── nginx.conf          # Nginx 配置（可选）
├── start.sh            # 启动脚本
├── requirements.txt     # Python 依赖
├── .gitignore          # Git 忽略配置

视频数据 (/opt/workspace/data/) ⚠️ 不上传 GitHub
├── videos/              # 视频存储目录
└── temp/               # 临时处理目录
```

## 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SERVER_HOST` | `http://YOUR_SERVER_IP:5000` | **必填**：服务器 IP 地址 |
| `WORKSPACE_DIR` | `/root/projects` | 项目代码目录 |
| `DATA_DIR` | `/opt/workspace/data` | 视频数据目录（可选） |

---

## 服务器配置步骤

### 1. 修改 SERVER_HOST

在部署前，您**必须**修改 `app.py` 中的 `SERVER_HOST` 为您的服务器 IP：

```python
# 编辑 app.py 第 27 行
SERVER_HOST = os.environ.get('SERVER_HOST', 'http://YOUR_SERVER_IP:5000')
```

替换 `YOUR_SERVER_IP` 为您的实际服务器 IP 地址，例如：
- `http://XXX.XXX.XXX.XXX:XXXX`

或者通过环境变量设置：
```bash
export SERVER_HOST=http://YOUR_SERVER_IP:5000
```

### 2. 创建必要目录

```bash
# 创建项目目录
sudo mkdir -p /root/projects

# 创建视频数据目录
sudo mkdir -p /opt/workspace/data/videos
sudo mkdir -p /opt/workspace/data/temp

# 设置权限
sudo chmod 777 /opt/workspace/data/videos
sudo chmod 777 /opt/workspace/data/temp
sudo chmod 777 /root/projects/data/uploads
```

### 3. 配置目录映射（可选）

由于项目代码在 `/root/projects/`，视频数据在 `/opt/workspace/data/`，
您可以通过软链接让代码访问视频数据：

```bash
# 在 /root/projects/ 下创建软链接
ln -s /opt/workspace/data/videos /root/projects/data/videos
ln -s /opt/workspace/data/temp /root/projects/data/temp
```

或者修改 `app.py` 中的路径配置：

```python
# 修改 app.py 第 28-31 行
WORKSPACE_DIR = os.environ.get('WORKSPACE_DIR', '/root/projects')
VIDEO_FOLDER = f'{WORKSPACE_DIR}/data/videos'
UPLOAD_FOLDER = f'{WORKSPACE_DIR}/data/uploads'
TEMP_FOLDER = f'{WORKSPACE_DIR}/data/temp'
```

改为：

```python
WORKSPACE_DIR = os.environ.get('WORKSPACE_DIR', '/root/projects')
VIDEO_FOLDER = '/opt/workspace/data/videos'
UPLOAD_FOLDER = f'{WORKSPACE_DIR}/data/uploads'
TEMP_FOLDER = '/opt/workspace/data/temp'
```

---

## 安装

### 基础依赖

```bash
# 安装 FFmpeg
sudo apt update
sudo apt install ffmpeg

# 安装 Python 依赖
cd /root/projects
pip install -r requirements.txt
```

### 启动服务

```bash
# 方式1：使用启动脚本
chmod +x start.sh
./start.sh

# 方式2：直接运行
python app.py
```

服务运行后访问：`http://YOUR_SERVER_IP:5000`

---

## 转码参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 视频编码 | H.264 (libx264) | VRCHAT 最佳兼容 |
| 质量 | CRF 18 | 高质量 |
| 音频编码 | AAC | 192kbps, 48kHz, 立体声 |
| 容器 | MP4 | +faststart 流媒体优化 |

---

## API 接口

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` | Web 上传界面 |
| POST | `/api/upload` | 上传视频 |
| GET | `/api/videos` | 获取视频列表 |
| GET | `/api/video/<id>/status` | 获取处理状态 |
| DELETE | `/api/video/<id>` | 删除视频 |
| GET | `/stream/<filename>` | 流媒体播放 |

---

## VRCHAT 使用

1. 通过 Web 界面上传视频
2. 等待转码完成（状态显示 Ready）
3. 点击复制获取视频 URL
4. 在 VRCHAT 世界中设置 VideoPlayer URL

---

## CLI 工具

```bash
# 上传视频
python upload.py upload /path/to/video.mkv

# 指定名称
python upload.py upload /path/to/video.mkv -n "My Video"

# 指定文件夹
python upload.py upload /path/to/video.mkv -f "VRChat Worlds"

# 列出所有视频
python upload.py list

# 扫描新文件
python upload.py scan
```

---

## License

MIT Licensese
