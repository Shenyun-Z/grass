# 生草机 (Grass Machine)

多语种中转翻译，制造"生草"文本。当前版本：**v1.6**（`python main.py --version` 可查看）。

## 原理

输入文本按逗号、句号切分，以设定字数为阈值：累计到阈值后，在最近的标点处切段。每个段依次经过多种语言翻译（如 中文→英语→法语→俄语→日语→...→中文），每经过一种语言词义就产生一次漂移，最终得到面目全非但莫名能读通的"生草"文本。

## 环境

```bash
conda create -n grass python=3.10 -y
conda activate grass
pip install -r requirements.txt
```

模型本地部署，**按模型目录里 `config.json` 的 `architectures` 自动识别后端**，两种都支持：

| 后端 | 默认目录 | 参数 | 语种 | 许可 | 说明 |
|---|---|---|---|---|---|
| **M2M-100**（默认，v1.7 起） | `m2m100_model/` | 418M | 100（本程序暴露 76 个常用） | MIT | "直译味"重，生草效果明显，CPU 快一个量级 |
| Hy-MT2 | `hymt2_model/` | 1.8B | 38（含繁体/粤语/藏/维） | Apache-2.0 | 质量太高，几乎不生草；适合要"准确"的场景 |

下载（ModelScope，国内直连）：

```bash
pip install modelscope

# 默认后端 M2M-100（约 1.9GB）
modelscope download --model facebook/m2m100_418M --local_dir .\m2m100_model

# 可选后端 Hy-MT2（约 3.9GB）
modelscope download --model Tencent-Hunyuan/Hy-MT2-1.8B --local_dir .\hymt2_model
```

语言列表会跟着后端变：M2M-100 没有繁体中文、粤语、藏语、维吾尔语，选这些会在翻译时被拒绝（界面列表里也不会出现）。

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

> 提示：Hy-MT2-1.8B 在 CPU 上逐句推理较慢（生草流程一次要跑几十上百次翻译）；M2M-100-418M 是编码器-解码器结构，同一个 CPU 上快一个量级。
>
> **CPU 实测参考**（Ryzen 9 7950X / 32 线程 / 无 GPU / float32）：
> M2M-100-418M 加载约 6.5 秒、单句 0.9–1.2 秒、2 段 × 5 轮（12 次调用）约 11 秒；
> Hy-MT2-1.8B 加载 31–46 秒、单句 3–7 秒、一段 3 轮中转约 36 秒。

## Windows 免安装版（exe）

Release 里附带 `grass-v1.6-win64.zip`，解压后双击 `生草机.exe` 即可运行，**不需要装 Python**。

- 包里**不含模型权重**（约 3.9GB）。首次运行前把 `hymt2_model\` 放到 `生草机.exe` 同级目录，
  或用 `HYMT2_MODEL_PATH` 指向模型目录；详细步骤见包内 `模型下载说明.txt`
- 下载：`modelscope download --model Tencent-Hunyuan/Hy-MT2-1.8B --local_dir .\hymt2_model`
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

> 提示：拖放是增强功能。`tkinterdnd2` 或 tkdnd 扩展不可用时会自动降级（拖放失效，其余功能不受影响），不会影响启动。
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
| Escape | 停止翻译 |

## 开发与测试

```bash
pip install -r requirements-dev.txt
pytest            # 84 个用例，覆盖分段、语言链、提示词与输出清理、语言表一致性、配置名校验、历史记录规整、文件读取与导出转义
```

测试不需要模型权重与 GPU：`hymt2.py` 的 `torch` / `transformers` 为惰性导入，逻辑层测试通过
`monkeypatch` 替换 `translate_batch`，模型缺失不会影响 GUI 启动（界面会给出缺失提示）。

## 项目结构

```
grass/
├── main.py              # 入口（--version 打印版本）
├── version.py           # 版本号唯一来源
├── gui.py               # 主应用（Mixin 组合模式）
├── gui_split_view.py    # 分块预览组件（控件池复用）
├── gui_compare.py       # 对照视图组件（双栏卡片对比）
├── gui_utils.py         # 工具 Mixin（Toast、颜色动画）
├── gui_lang.py          # 语言管理 Mixin（语言选择、预设、随机模式）
├── gui_config.py        # 配置管理 Mixin（保存、加载、导入、导出、删除）
├── gui_translate.py     # 翻译控制 Mixin（启动、停止、消息轮询）
├── gui_dialogs.py       # 弹窗（语言选择、排除语言、预设、翻译过程详情、历史记录、切分标点设置）
├── gui_styles.py        # 设计系统（颜色、字体、样式函数）
├── engine.py            # 翻译流程编排（分段、语言链、进度事件）
├── hymt2.py             # Hy-MT2 本地推理封装（提示词、采样参数、输出清理）
├── languages.py         # 语言白名单与 Hy-MT2 语言映射
├── validators.py        # 输入校验与安全辅助（无 GUI/torch 依赖，可单测）
├── tests/               # pytest 用例
├── hymt2_model/         # Hy-MT2 本地模型文件（不入库）
├── requirements.txt     # 运行依赖（已加版本区间）
├── LICENSE              # 代码许可（MIT）
└── configs/             # 用户保存的配置文件
```

**架构说明**：`App` 类通过 Mixin 组合模式拆分职责，每个 Mixin 专注单一功能，降低耦合度，便于维护和扩展。

## 预设语言

| 预设 | 语言 |
|------|------|
| 大语种 | 英语、法语、俄语、日语、西班牙语、德语、阿拉伯语 |
| 亚洲 | 日语、韩语、泰语、越南语、印尼语、印地语、阿拉伯语 |
| 欧洲 | 英语、法语、德语、西班牙语、俄语、意大利语、葡萄牙语 |
| 民族语言 | 藏语、蒙古语、维吾尔语、哈萨克语 |
| 随机混合 | 从 5 个地区各随机抽 1 个语言 |

## 支持语言

共 38 个语种/变体（与 Hy-MT2 官方语言表一致）：中文、繁体中文、粤语、日语、韩语、蒙古语、藏语、泰语、越南语、印尼语、马来语、菲律宾语、缅甸语、高棉语、印地语、孟加拉语、乌尔都语、泰米尔语、泰卢固语、马拉地语、古吉拉特语、阿拉伯语、希伯来语、波斯语、土耳其语、哈萨克语、维吾尔语、英语、法语、德语、西班牙语、葡萄牙语、意大利语、俄语、乌克兰语、波兰语、捷克语、荷兰语。详见 [languages.py](languages.py)。

## 许可

- 本仓库代码：MIT，见 [LICENSE](LICENSE)。
- 模型权重：**Apache-2.0**，由腾讯混元开源（`tencent/Hy-MT2-1.8B`）。商用与再分发请遵循模型卡与 Apache-2.0 条款，并保留出处。
- 模型引用：

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