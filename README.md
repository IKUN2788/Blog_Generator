<img width="1912" height="1017" alt="image" src="https://github.com/user-attachments/assets/a743acfd-3c04-4964-974a-4a4fded99c4a" />

# 灵感火花 SparkSeek

基于 AI 驱动的批量文章生成工具，可根据给定主题（Seed）生成高质量的中文博客文章。

## 功能特性

### 文章生成
- 🎯 基于主题/标签批量生成文章
- 🔄 支持顺序/随机生成模式
- ⚡ 多线程并发生成（可配置 1-10 线程）
- 📊 实时进度显示和速率限制

### 文章管理
- 📝 文章列表查看（分页）
- 🔍 文章详情查看（Markdown 渲染）
- 🗑️ 单篇/批量删除
- ✨ 一键修正（去重、清理失败记录）
- 🔢 ID 重排（按创建时间重新排序）

## 已支持的 AI 模型
- **Xiaomi Mimo v2 Flash**

## 项目结构

```
灵感火花 SparkSeek/
├── app.py                 # Flask 主应用
├── requirements.txt       # 依赖包列表
├── README.md             # 项目说明文档
│
├── core/                 # 核心业务模块
│   ├── __init__.py
│   ├── generator.py      # 文章生成器（协调器）
│   ├── database.py       # 数据库操作（SQLite）
│   └── api_client.py     # MiMo API 客户端
│
├── utils/                # 工具模块
│   ├── __init__.py
│   └── config.py         # 配置管理（加密存储）
│
├── static/               # 静态资源
│   ├── css/             # 样式文件
│   ├── js/              # JavaScript 文件
│   └── webfonts/        # 字体文件
│
├── templates/            # HTML 模板
│   └── index.html       # 主页面
│
└── data/                 # 数据文件
    ├── articles.db      # 文章数据库
    ├── tags.json        # 标签配置
    └── config.enc       # 加密配置文件
```

## 技术栈

### 后端
- **Flask** - Web 框架
- **SQLite** - 数据库
- **OpenAI SDK** - API 调用
- **Cryptography** - 配置加密

### 前端
- **Tailwind CSS** - UI 框架
- **Alpine.js** - 响应式框架
- **markdown-it** - Markdown 渲染
- **highlight.js** - 代码高亮

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

启动应用后，点击右上角"设置"按钮，输入 MiMo API Key。

### 3. 启动应用

```bash
python app.py
```

应用会自动打开浏览器访问 http://127.0.0.1:5000

## 使用说明

### 生成文章

1. 选择或输入主题/标签
2. 设置生成数量和文章长度
3. 点击"开始"按钮
4. 实时查看生成进度

### 管理文章

- **刷新** - 重新加载文章列表
- **修正** - 删除重复和失败的文章
- **ID重排** - 按创建时间重新分配 ID
- **清空** - 删除所有文章

### 查看文章

点击文章列表中的"查看"按钮，可以：
- 查看完整的 Markdown 渲染内容
- 复制文章内容到剪贴板

## 配置说明

### 标签配置 (data/tags.json)

```json
{
  "科技": ["人工智能", "机器学习", "云计算"],
  "生活": ["健康", "美食", "旅游"]
}
```

### 应用配置

- **API Key** - MiMo API 密钥
- **并发线程数** - 1-10，建议 3-5
- **速率限制** - 默认 100 请求/分钟

## 注意事项

1. 首次使用需要配置 API Key
2. 生成过程中请勿关闭浏览器
3. 建议定期使用"修正"功能清理数据
4. 数据库文件 `data/articles.db` 请勿手动修改

## 开发说明

### 模块职责

- **core/generator.py** - 文章生成协调器，管理生成流程
- **core/database.py** - 数据库操作，提供 CRUD 接口
- **core/api_client.py** - API 客户端，处理速率限制
- **utils/config.py** - 配置管理，加密存储敏感信息

## 许可证

MIT License
