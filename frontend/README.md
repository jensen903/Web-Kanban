# Frontend Prototype

这是网页看板的本地静态原型目录。

当前目标：

- 不依赖额外安装的前端框架
- 直接基于本地导出的 JSON 数据集渲染 5 个看板骨架
- 用于快速验证页面结构、信息层级和交互方式

目录说明：

- `index.html`
  - 单页原型入口
- `styles.css`
  - 页面样式
- `app.js`
  - 页面状态、筛选逻辑、模块渲染
- `data/dashboard_dataset.json`
  - 前端读取的轻量数据集

当前限制：

- 这不是最终技术栈实现版
- 当前不接正式 HTTP API
- 当前主要用于本地演示和页面结构确认

本地预览：

```bash
python3 /Users/apple/窄巷口/网页看板/frontend/serve_preview.py
```

然后在浏览器打开：

`http://127.0.0.1:4173`
