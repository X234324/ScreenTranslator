# 🚀 Skylark Screen Translator

## Automatic Windows screen translation mode

This fork adds an offline automatic mode in `auto_mode.py`. It monitors all
connected displays when launched, runs local Tesseract OCR only after a visible
screen change, and translates English text to Chinese with local Argos
models. It does not call online translation services. The overlay is
borderless, translucent, always on top, draggable from its header, and has a
Pause/Resume button. Use the mouse wheel over the overlay to adjust opacity.

### Windows setup

1. Install Python 3.11+ and Tesseract OCR with the English (`eng`) trained
   data. If Tesseract is not on `PATH`, set
   `TESSERACT_CMD` to the full path of `tesseract.exe`.
2. In PowerShell, from this folder, run:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe setup_models.py
   .\.venv\Scripts\python.exe auto_mode.py
   ```

The one-time model setup downloads the open Argos English-to-Chinese language
package from its public index; runtime screen capture, OCR, and translation
are local. The default monitor checks for changes every 0.7 seconds. The
overlay itself is excluded from OCR and change detection. Closing the overlay
stops the monitor.

<div align="center">

<img width="256" height="256" alt="Gemini_Generated_Image_c7lzf7c7lzf7c7lz" src="https://github.com/user-attachments/assets/695a5db9-c9c2-433c-984b-6aa2331d60dc" />


**✨ 由 AI 协作开发的智能屏幕翻译工具 ✨**

*像云雀一样自由飞翔，突破语言的边界*


![Peek 2025-08-05 16-47](https://github.com/user-attachments/assets/16277763-32dc-4d8e-9b62-36033055ed17)






</div>

---

## 🌟 为什么选择 Skylark？

🎯 **一键翻译任何屏幕内容** - 游戏、网页、文档、图片...随心所欲  
🧠 **AI 智能路径选择** - 自动寻找最快最准确的翻译路径  
🌍 **30+ 语言支持** - 涵盖主流语言，满足全球化需求  
⚡ **极速体验** - 离线OCR + 多引擎翻译，毫秒级响应  
🎨 **现代化界面** - 简约美观，操作直观，无学习成本  



## 🚀 核心特性

### 🎯 智能翻译系统
- **🔄 智能中转翻译** - 当直接翻译路径不存在时，自动选择最优中转路径
- **⚡ 多引擎融合** - 支持 Argos (离线) + LibreTranslate/Mymenory/Google/DeepL/百度/微软 (在线)
- **🧠 路径优化算法** - 优先使用直接翻译，提升速度和准确率

### 🖱️ 极简操作体验
- **框选翻译** - 左键拖拽框选，右键双击翻译
- **一键隐藏** - 左键单击显示/隐藏翻译窗口
- **滚轮浏览** - 鼠标滚轮查看完整翻译内容

### 🔧 强大的引擎支持

除了离线的 Argos Translate 引擎，Skylark 现在也支持 在线翻译服务，适用于更高精度或更多语言方向的翻译需求：
| 平台           | 是否需要 API 密钥     | 注册/获取地址                                                                           |
| ------------ | --------------- | --------------------------------------------------------------------------------- |
| 🌐 LibreTranslate 翻译 | ❌ 无需密钥          | 内置公共接口，无需注册                                                                       |
| 🌐 MyMemory 翻译 | ❌ 无需密钥          | 内置公共接口，无需注册                                                                       |
| 🌐 Google 翻译 |  ✅ 需要 API 密钥       |  [Google注册](https://cloud.google.com/translate)                                                                 |
| 🌐 DeepL 翻译  | ✅ 需要 API 密钥     | [DeepL Pro 注册](https://www.deepl.com/pro-api)                                     |
| 🌐 百度翻译      | ✅ 需要 APP ID 与密钥 | [百度翻译开放平台](https://fanyi-api.baidu.com/)                                          |
| 🌐 微软翻译   | ✅ 需要 API 密钥      | [注册获取密钥（Azure Portal）](https://azure.microsoft.com/products/cognitive-services/translator/) | 
 |


## ⚡ 5分钟快速开始（Linux）

### 📦 一键安装
```bash
# 下载并运行安装脚本
chmod +x Install_LinuxSkylarkTranslator.sh
./Install_LinuxSkylarkTranslator.sh
```


### 🎯 首次配置
1. **启动软件** - 点击桌面图标
2. **安装语言包** - 进入【语言包管理】，选择需要的翻译方向
3. **重启软件** - 在【设置语言】中选择翻译方向
4. **开始使用** - 框选屏幕区域，右键双击翻译！

### 🗑️ 一键卸载
```bash
chmod +x Uninstall_LinuxSkylarkTranslator.sh
./Uninstall_LinuxSkylarkTranslator.sh
```


## ⚡ 2分钟快速开始（Windows）

Windows版因为离线翻译argos translate需要的环境容量非常大，完全打包后无法分享！所以只有online版！

- 下载SkylarkTranslator_Windows_online后解压，无需安装即可使用！
- 第1次使用需要到软件内的语言包设置安装需要的ocr语言
- OCR语言包默认安装在用户文件夹内的APPDATA内！


---


## 🌍 支持的语言

**主流语言全覆盖**：英语 🇺🇸 | 中文 🇨🇳 | 日语 🇯🇵 | 韩语 🇰🇷 | 法语 🇫🇷 | 德语 🇩🇪 | 西班牙语 🇪🇸 | 俄语 🇷🇺 | 意大利语 🇮🇹 | 葡萄牙语 🇵🇹

**30+ 语言完整支持** - 你可以自由组合任意语言对，Skylark 的智能路径系统会自动处理所有技术细节！

## 🧠 AI 智能中转翻译

### 🔄 智能路径选择算法

```
情况1: 直接翻译路径存在
日语 → 中文 ✅ 直接翻译（最快最准）

情况2: 需要中转翻译
日语 → 中文 ❌ 直接路径不存在
↓ AI自动选择最优路径
日语 → 英语 → 中文 ✅ 自动中转翻译
```

**🎯 零配置智能化** - 你只需要选择"我要从日语翻译到中文"，剩下的路径规划全部交给 Skylark！

## 💻 技术架构

### 🏗️ 核心技术栈
- **🐍 Python + PyQt5** - 现代化桌面应用开发
- **👁️ Tesseract OCR** - Google 出品的开源OCR引擎
- **🌐 Argos Translate** - 高质量离线翻译引擎
- **🔗 多API集成** - 统一的在线翻译服务接口

### ⚙️ 系统要求
- **🐧 操作系统**: Linux (推荐 Ubuntu/Debian) / Windows
- **💾 处理器**: 支持 SSE4.1 指令集
- **🌐 网络**: 可选（离线翻译无需网络）

## 🤝 开发故事

这个项目是 **DeepSeek** 和 **Claude** 两个AI助手协作开发的成果，展现了AI协作开发的无限可能：

- 🧠 **智能算法设计** - AI设计的路径选择算法
- 🎨 **用户体验优化** - AI优化的界面和交互设计  
- 🔧 **代码架构** - AI协作完成的模块化架构
- 📚 **文档编写** - AI编写的详细文档和说明

## 🙏 鸣谢

- 💬 [Argos Translate](https://github.com/argosopentech/argos-translate) — 开源的高质量离线翻译引擎  
- 👓 [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — Google 出品的 OCR 引擎  
- 🎨 [Qt](https://www.qt.io/) + [PyQt5](https://riverbankcomputing.com/software/pyqt/intro) — 现代化图形界面开发库

### 🌐 在线翻译服务鸣谢

- 🌐 [MyMemory 翻译](https://mymemory.translated.net/) — 使用公开接口实现在线翻译（无需 API 密钥）
- 🌐 [LibreTranslate 翻译](https://libretranslate.com/) — 使用公开接口实现在线翻译（无需 API 密钥）
- 🌐 [Google 翻译](https://cloud.google.com/translate) —  高质量神经翻译服务（通过 API 接入）
- 🌐 [DeepL 翻译](https://www.deepl.com/pro-api) — 高质量神经翻译服务（通过 API 接入）  
- 🌐 [百度翻译](https://fanyi-api.baidu.com/) — 百度开放平台提供的翻译 API 接口  
- 🌐 [Microsoft Translator](https://azure.microsoft.com/products/cognitive-services/translator/) — Azure 提供的多语言在线翻译服务



## 📄 开源协议 (License)

本项目根据 **GNU General Public License v3.0 (GPLv3)** 授权。

简单来说，这意味着你可以自由地：
* **运行** 本软件用于任何目的。
* **修改** 本软件的源代码。
* **分发** 本软件的原始或修改后的版本。

但是，你也必须遵守以下核心条件：
* **同样保持开源 (Copyleft)**：如果你修改并分发了此软件，你的修改版本也**必须**使用 GPLv3 许可证授权。
* **提供源代码**：你必须向接收者提供你的（修改后）版本的完整源代码。
* **保留许可证和版权声明**：你必须保留原始的版权和许可证声明。

**重要提示**：本软件是“按原样”提供的，**不提供任何形式的保证**，作者**不对任何损害承担责任**。完整的法律条款请参见项目中的 `LICENSE` 文件。

### 📦 依赖项许可证
本软件依赖于以下项目，它们各自的许可证决定了本项目必须使用 GPLv3：
* **PyQt5**: GPL v3
* **Argos Translate**: AGPL v3
* **Tesseract OCR**: Apache 2.0
* (以及其他 Python 库各自的许可证...)


### 💻 AI 开发说明
本项目使用 AI 工具 (DeepSeek 和 Claude 4) 辅助开发。GPLv3 许可证适用于项目中体现了作者（Jt Liaw）创造性劳动的整体作品。
---
<div align="center">

*像云雀一样自由翱翔，在语言的天空中无拘无束* 🦅

</div>
