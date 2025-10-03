FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

RUN apt update && apt install -y --no-install-recommends \
    # 编译工具
    gcc \
    g++ \
    musl-dev \
    python3-dev \
    libffi-dev \
    unzip \
    git \
    curl \
    # 图像处理和压缩库（用于 Pillow / OpenCV headless）
    libpng-dev \
    libjpeg-dev \
    libglib2.0-0 \
    # lxml 依赖
    libxml2-dev \
    libxslt1-dev \
    # 字体显示
    fontconfig \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    # 网络工具
    net-tools \
    && rm -rf /var/lib/apt/lists/* \
    && apt clean

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Node.js
RUN apt-get update && apt-get install -y curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

RUN npm install -g pnpm

# Install Vercel CLI
RUN npm install -g vercel

# 复制项目文件
COPY . .

# 暴露端口
EXPOSE 8123

# 启动命令
CMD ["python", "run.py"]
