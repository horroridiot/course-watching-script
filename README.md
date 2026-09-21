# 学习通自动化助手 (Chaoxing Automation Helper)

本项目基于 Python + Playwright + OpenAI 兼容接口，用于自动化处理学习通课程任务。
支持：自动播放视频、AI 自动答题（单选/多选/判断/填空）、防跳章节、多视频处理。

## ⚠️ 免责声明
本项目仅供学习 Python 自动化和 Playwright 技术使用，请勿用于违反平台规定的行为。使用本脚本产生的任何后果（包括但不限于账号封禁、成绩无效等）由使用者自行承担。

## 环境要求
*   Python 3.8 或更高版本
*   Google Chrome / Edge（Playwright 会自动下载 Chromium）

## 安装步骤
1. 安装 Python 依赖库：
   ```bash
   pip install playwright openai -i https://pypi.tuna.tsinghua.edu.cn/simple
