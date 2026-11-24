# 生草机 (Grass Machine)

多语种中转翻译，制造"生草"文本。当前版本：**v2.0**（`python main.py --version` 可查看）。

> **v2.0 起界面用 PySide6（Qt）完全重写**：分块预览与对照视图改成虚拟化列表，拖动窗口、滚动、流式出结果都不再重排整棵控件树；并新增 Ctrl+滚轮调字号。

## 原理

输入文本按逗号、句号切分，以设定字数为阈值：累计到阈值后，在最近的标点处切段。每个段依次经过多种语言翻译（如 中文→英语→法语→俄语→日语→...→中文），每经过一种语言词义就产生一次漂移，最终得到面目全非但莫名能读通的"生草"文本。

## 环境

```bash
conda create -n grass python=3.10 -y
conda activate grass
pip install -r requirements.txt
```

模型本地部署，**按模型目录里 `config.json` 的 `architectures` 自动识别后端**，三种都支持：

| 后端 | 默认目录 | 参数 | 语种 | 许可 | 说明 |
|---|---|---|---|---|---|
| **MiLMMT-46**（默认，v1.7 起） | `milmmt_model/` | 1B | 46（含繁体中文/粤语，无藏/维/蒙） | Gemma | 质量明显高于 M2M、低于 Hy-MT2，翻译稳定不吐占位符 |
| M2M-100 | `m2m100_model/` | 418M | 100（本程序暴露 76 个常用） | MIT | "直译味"最重、生草最狠，CPU 最快，但会丢词 |
| Hy-MT2 | `hymt2_model/` | 1.8B | 38（含繁体/粤语/藏/维） | Apache-2.0 | 质量太高，几乎不生草；适合要"准确"的场景 |

下载（ModelScope，国内直连）：

```bash
pip install modelscope

# 默认后端 MiLMMT-46-1B（约 2.0GB）
modelscope download --model xiaomi-research/MiLMMT-46-1B-v1.0 --local_dir .\milmmt_model

# 可选后端 M2M-100（约 1.9GB）
modelscope download --model facebook/m2m100_418M --local_dir .\m2m100_model

# 可选后端 Hy-MT2（约 3.9GB）
modelscope download --model Tencent-Hunyuan/Hy-MT2-1.8B --local_dir .\hymt2_model
```

语言列表会跟着后端变：MiLMMT-46 有繁体中文、粤语，但没有藏语、维吾尔语、蒙古语；M2M-100 连繁体中文和粤语也没有。选不支持的语言会在翻译时被拒绝（界面列表里也不会出现）。

> MiLMMT-46 的指令跟随能力在后训练阶段被大幅削弱，官方要求用固定提示词并显式写出源语言（没有自动识别模式）。程序已按官方格式拼 `Translate this from <源语言> to <目标语言>:`，并给语言名做了官方的英文名映射，不要自己改提示词。

> **安全提示**：模型目录的 `config.json` 由 `transformers` 解析，请只使用可信来源的模型；
> 目录内若存在 `*.safetensors` 权重，程序会强制优先使用，避免 pickle 反序列化带来的代码执行风险。
> 默认**不**开启 `trust_remote_code`；确认为可信来源且模型确实需要时，才设置 `GRASS_HYMT2_TRUST_REMOTE_CODE=1`。

**自定义模型路径**：设置环境变量 `GRASS_MODEL_PATH`（旧写法 `HYMT2_MODEL_PATH` 继续兼容）可指定模型位置，例如：
```bash
set GRASS_MODEL_PATH=D:\models\m2m100_model    # Windows
export GRASS_MODEL_PATH=/path/to/m2m100_model  # Linux/macOS
```

**设备与精度**：程序自动检测 CUDA，有显卡时用 GPU + bfloat16（不支持时退 float16）推理，CPU 则用 float32；每段翻译后自动释放显存缓存。也可用 `GRASS_DEVICE` 强制指定：
```bash
set GRASS_DEVICE=cpu    # 强制使用 CPU
set GRASS_DEVICE=cuda   # 强制使用 GPU（无显卡时会报错）
```

> 提示：MiLMMT-46 是解码器模型，逐 token 生成，CPU 上比 M2M-100 慢；生草流程一次要跑几十上百次翻译，段落多时会明显等。
>
> **CPU 实测参考**（Ryzen 9 7950X / 32 线程 / 无 GPU / float32）：
> MiLMMT-46-1B 加载约 3 秒、单句 2.8–4.3 秒、3 轮中转约 14 秒、5 轮约 22 秒；
> M2M-100-418M 加载约 6.5 秒、单句 0.9–1.2 秒、2 段 × 5 轮（12 次调用）约 11 秒；
> Hy-MT2-1.8B 加载 31–46 秒、单句 3–7 秒、一段 3 轮中转约 36 秒。

## Windows 免安装版（exe）

Release 里附带 `grass-v2.0-win64.zip`，解压后双击 `生草机.exe` 即可运行，**不需要装 Python**。解压到中文目录（如 `生草机\`）或纯英文目录都可以。

- 包里**不含模型权重**（约 2.0GB）。首次运行前把 `milmmt_model\` 放到 `生草机.exe` 同级目录，
  或用 `GRASS_MODEL_PATH` 指向模型目录；详细步骤见包内 `模型下载说明.txt`
- 下载：`modelscope download --model xiaomi-research/MiLMMT-46-1B-v1.0 --local_dir .\milmmt_model`
- 默认 CPU 推理（构建的 exe 不带 CUDA 运行库）；有显卡想用 GPU 的走源码安装路径
- 自己打包：`powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1`
  （需先 `pip install pyinstaller`，产物在 `dist\`）

## 用法

```bash
conda activate grass
python main.py
```

启动后按以下步骤操作：

| 步骤 | 操作 | 对应区域 |
|------|------|----------|
| 1 | 输入文本（或点击"从文件读取"/"读剪贴板"，或拖放 .txt 文件） | **输入**：支持原文/去空格切换；一键读入剪贴板；可拖动下边界调整高度；聚焦时边框高亮 |
| 2 | 设置中转轮数（1-30）、每段字数（5-100）、最终译回语言、翻译模式 | **参数**：紧凑一行布局，支持固定/低强度/高强度三种模式 |
| 3 | 选择中转语言序列（点击"语言预设"可快速选择分组） | **中转语言**：流式展示语言序列；完整翻译链显示（中文→英语→法语→...→中文）；点击可修改；支持配置保存/加载/导入/导出/删除 |
| 4 | 查看分块预览确认分段；点击"切分符..."可配置分段标点 | **分块预览**：实时显示文本分段；支持逗号/句号/叹号/问号/分号/冒号/顿号及自定义分隔符；段号醒目；默认并排显示原文与翻译结果；可拖动下边界调整高度；翻译时也可缩放；自动跟随当前翻译段 |
| 5 | 点击"开始翻译"或按 Ctrl+Enter（输入框内不触发） | **控制**：开始/停止按钮（模型加载期间禁用）；状态文字 |
| 6 | 实时查看进度和当前翻译步骤 | **进度**：严格逐句翻译（一段完成前不开始下一段），平滑动画进度条、段完成计数、当前步骤，段落逐句实时变绿 |
| 7 | 翻译完成后点击段落卡片查看完整翻译过程 | 弹出翻译过程详情窗口 |
| 8 | 复制或保存结果；切换"对照"视图按段对比 | **结果**：结果/对照双视图；对照视图支持"原文 vs 当前结果"或"任意历史结果 vs 当前结果"按段对比 |
| 9 | 点击"历史"回看最近 N 次处理结果 | **历史**：内存保留最近 20 次记录；查看原文/结果/参数详情；支持复制结果、删除单条、清空、一键对照查看 |

> 提示：拖放由 Qt 原生支持，拖入 .txt 文件即可读入；不需要额外安装插件。
>
> 提示：翻译完成后默认**不自动覆盖剪贴板**。若需完成后自动复制结果，勾选控制栏"完成后自动复制"开关。
>
> 提示：历史记录会持久化到本地 `history.json`，程序退出后重新打开仍可回看。

## 翻译模式

| 模式 | 说明 |
|------|------|
| 固定 | 按设定的中转语言序列依次翻译 |
| 低强度 | 每轮从大语种中随机选择一种语言翻译 |
| 高强度 | 每轮从全部 38 个语种中随机选择一种翻译 |

随机模式下可点击"排除语言..."按钮，勾选不想参与随机的语言（如英语翻译太准确，排除后生草效果更显著）。

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+Enter | 开始/停止翻译（输入框内不拦截） |
| Ctrl+S | 保存结果 |
| Ctrl+Shift+V | 从剪贴板读入输入区 |
| Ctrl+H | 打开历史记录 |
| Ctrl+滚轮 / Ctrl+= / Ctrl+- | 调字号（80%~180%，圆角与间距等比缩放） |
| Ctrl+0 | 字号恢复 100% |
| Escape | 停止翻译 |

## 界面性能（v2.0）

v1.x 的卡顿来自「一个 Canvas 里塞整棵控件树 + 每段一套卡片控件 + 每次更新全量重排」。v2.0 的对应改动：

| 问题 | v2.0 做法 |
|------|-----------|
| 滚动整棵树重绘 | 分块/对照列表改为 `QListView` + 自绘 delegate，只画视口内 1~2 屏 |
| 每段一个复合控件 | 不再有控件，行是绘制出来的矩形 + 文字 |
| 每次结果全量重排 | 某段到达时只对该行发 `dataChanged`，其余行不动 |
| 拖动窗口一顿一顿 | 行高按「行号 + 32px 宽度桶 + 内容版本」缓存，跨桶才重算；布局由 Qt 增量完成 |
| 滚轮发涩 | 逐像素滚动，滚轮步长固定 66px（可感知 Ctrl+滚轮缩放） |
| 500ms 防抖重排 | 去掉防抖，缩放/拉伸实时跟随 |

离屏实测（600 段、单窗口 900×420 列表）：首次布局 8.5ms，600 段逐段更新合计 2.4ms，
连续 60 次拉伸平均 13ms/次（200 段约 7ms/次）；整窗拉伸平均约 7ms/次。

## 开发与测试

```bash
pip install -r requirements-dev.txt
pytest            # 120 个用例：分段/语言链/提示词/输出清理/配置名/历史规整/文件读取/界面冒烟
```

界面测试用 `QT_QPA_PLATFORM=offscreen` 离屏运行，不需要显示器；也不会加载真实模型权重
（设 `GRASS_SKIP_MODEL_LOAD=1` 跳过加载，`GRASS_DATA_DIR` 指定临时数据目录，避免写仓库里的 history.json）。

## 项目结构

```
grass/
├── main.py              # 入口（--version 打印版本、打包版日志重定向）
├── version.py           # 版本号唯一来源
├── grass_ui/            # v2.0 界面层（PySide6）
│   ├── app.py           # QApplication 创建、调色板与主题
│   ├── mainwindow.py    # 主窗口：状态、输入、翻译流程、历史、配置
│   ├── panes.py         # 七个功能面板（输入/参数/语言/分块/控制/进度/结果）
│   ├── splitview.py     # 分块与对照的虚拟化列表（模型 + delegate）
│   ├── dialogs.py       # 七个弹窗（语言/排除/预设/过程/删配置/历史/切分符）
│   ├── widgets.py       # 卡片、流式布局、分段按钮、Toast、拖高手柄
│   ├── theme.py         # 配色、字体、QSS（支持整体缩放）
│   └── paths.py         # 数据目录（exe 同级 / 仓库根）
├── engine.py            # 翻译流程编排（分段、语言链、进度事件）
├── milmmt.py            # MiLMMT-46 本地推理封装（官方固定提示词、语言名映射、输出清理）
├── m2m100.py            # M2M-100 本地推理封装
├── hymt2.py             # Hy-MT2 本地推理封装（提示词、采样参数、输出清理）
├── backend.py           # 按 architectures 路由到具体后端
├── modelpath.py         # 模型目录探测与后端识别
├── pathmirror.py        # 非 ASCII 路径下的分词器镜像
├── langdata.py          # 各后端的语言表、分组与预设
├── languages.py         # 语言白名单（随后端裁剪）
├── validators.py        # 输入校验与安全辅助（无 GUI/torch 依赖，可单测）
├── tests/               # pytest 用例
├── requirements.txt     # 运行依赖（已加版本区间）
├── LICENSE              # 代码许可（MIT）
└── configs/             # 用户保存的配置文件
```

**架构说明**：业务逻辑（`engine` / 后端封装 / `languages` / `validators`）与界面完全解耦，
`grass_ui` 只负责呈现与交互；因此换界面框架不影响翻译流程，反之亦然。

## 预设语言

| 预设 | 语言 |
|------|------|
| 大语种 | 英语、法语、俄语、日语、西班牙语、德语、阿拉伯语 |
| 亚洲 | 日语、韩语、泰语、越南语、印尼语、印地语、阿拉伯语 |
| 欧洲 | 英语、法语、德语、西班牙语、俄语、意大利语、葡萄牙语 |
| 华语变体（MiLMMT） | 中文、繁体中文、粤语 |
| 中亚民族（MiLMMT/M2M-100） | 哈萨克语、乌兹别克语、阿塞拜疆语、土耳其语 |
| 民族语言（Hy-MT2） | 藏语、蒙古语、维吾尔语、哈萨克语 |
| 随机混合 | 从 5 个地区各随机抽 1 个语言 |

## 支持语言

界面列表随当前后端变化，详见 [languages.py](languages.py) 与 [langdata.py](langdata.py)：

- **MiLMMT-46（默认，46 个）**：中文、繁体中文、粤语、日语、韩语、泰语、越南语、印尼语、马来语、菲律宾语、缅甸语、高棉语、老挝语、印地语、孟加拉语、泰米尔语、乌尔都语、阿拉伯语、希伯来语、波斯语、土耳其语、哈萨克语、阿塞拜疆语、乌兹别克语、英语、法语、德语、西班牙语、葡萄牙语、意大利语、俄语、荷兰语、波兰语、捷克语、斯洛伐克语、斯洛文尼亚语、克罗地亚语、保加利亚语、罗马尼亚语、匈牙利语、希腊语、丹麦语、瑞典语、芬兰语、挪威语、加泰罗尼亚语
- **M2M-100**：100 个语言代码，程序暴露 76 个常用（无繁体中文/粤语/藏语/维吾尔语）
- **Hy-MT2**：38 个语种/变体（上面那套 + 蒙古语、藏语、维吾尔语、乌克兰语等）

## 许可

- 本仓库代码：MIT，见 [LICENSE](LICENSE)。
- **默认模型权重**：`xiaomi-research/MiLMMT-46-1B-v1.0`，由小米 MiLM Plus 开源，遵循 **Gemma 许可**（基于 `google/gemma-3-1b-pt`）。商用与再分发请阅读模型卡与 Gemma 条款，并保留出处。
- 可选模型：`facebook/m2m100_418M`（MIT）、`tencent/Hy-MT2-1.8B`（Apache-2.0）。
- MiLMMT 模型引用：

```bibtex
@misc{han2026referencefreeposttrainingopenlarge,
  title={Reference-Free Post-Training of Open Large Language Models for Multilingual Machine Translation},
  author={Chris Han and Pengzhi Gao and Pei Fu and Jian Luan},
  year={2026},
  eprint={2608.10812},
  archivePrefix={arXiv},
  primaryClass={cs.CL},
  url={https://arxiv.org/abs/2608.10812}
}
```

- Hy-MT2 模型引用：

```bibtex
@misc{zheng2026hymt2familyfastefficient,
  title={Hy-MT2: A Family of Fast, Efficient and Powerful Multilingual Translation Models in the Wild},
  author={Mao Zheng and Zheng Li and Tao Chen and Bo Lv and Mingrui Sun and Mingyang Song and Jinlong Song and Hong Huang and Decheng Wu and Hai Wang and Yifan Song and Yanfeng Chen and Guanwei Zhang},
  year={2026},
  eprint={2605.22064},
  archivePrefix={arXiv},
  primaryClass={cs.CL}
}
```