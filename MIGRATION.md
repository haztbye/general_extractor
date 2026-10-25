# 个人版改造方案（企业版 → 个人可用版）

> 改造日期：2026-10-25
> 本仓库只保留本地化重构版；更早的企业服务时期版本不包含在公开历史中。

## 1. 为什么要改

企业版依赖以下**个人无法访问**的内部设施，离开公司环境后完全无法运行：

| 依赖 | 用途 | 个人版替代 |
|---|---|---|
| `contractlib`（内部 git+ssh 仓库） | FormDoc 数据结构、文档迭代 API | 自建 `document_parsing` 模块（等价数据模型 + 兼容 API） |
| 内部 OCR gRPC 服务 | PDF → FormDoc（带字符坐标） | **PyMuPDF** 本地解析（文本层 + 字符框 + 表格） |
| 内部 DOCX 解析 gRPC 服务 | DOCX → FormDoc | **python-docx** 本地解析 |
| `algorithm_service` pb2 包 | gRPC 服务接口（ElementExtractor 等） | 移除 gRPC 层，改为 **CLI + Python API** |
| 内部 LLM 代理服务 | 大模型调用 | 任意 **OpenAI 兼容 API**（智谱 / DeepSeek / OpenAI / Ollama 均可） |
| Jenkins / K8s / mage 工具链 | CI/CD | 删除（个人用不上） |

**技术栈保持不变**：Python + asyncio + Pydantic + loguru + environs + openai SDK，核心流水线（窗口切分 → LLM 抽取 → 定位 → 坐标 → 合并）一行逻辑不动，只换"地基"。

## 2. 架构对比

```
企业版：  Client → gRPC 服务 → [内部OCR/Parser] → FormDoc(contractlib) → core/core2 流水线 → 内部 LLM
个人版：  CLI / Python API  → [PyMuPDF/python-docx 本地解析] → FormDoc(自建等价模型) → 同一套 core/core2 流水线 → 你自己的 OpenAI 兼容 key
```

## 3. 改动清单

### 新增
- `extractor_pdf/document_parsing/` —— contractlib 的本地等价物
  - `models.py`：`FormDoc / Section / Table / Row / Cell / Rect / CharRects / CharRect`，属性形状与 contractlib 一致（`section.id / .rects / .char_rects`、`rects[0].page_id`、`char_rects[0].rect_list[i].coord/.page_id`、`table.rows[].cells[].children[]`）
  - `form_doc.py`：兼容 API —— `formdoc_iter() / get_section_text() / is_table() / get_section_by_id() / parse() / new_formdoc_from_path()`
  - `pdf_parser.py`：PyMuPDF 解析 PDF（文本块 → 段落 section；rawdict 字符级 bbox → char_rects；`find_tables()` → 表格结构）
  - `docx_parser.py`：python-docx 解析 DOCX（段落 + 表格按文档顺序；无版面坐标 → 按"显式分页符 + 每页段落数上限"估算伪页码，定位回退段落级）
- `extractor_pdf/proto_like.py` —— 替代 form_doc_pb2 的 `FormRes / LabelInfoList / LabelInfo / Position / Rect`（保持 `.add()/.extend()` 链式写法，纯 Python dataclass）
- `extractor_pdf/cli.py` + `__main__.py` —— 命令行入口：
  - `python -m extractor_pdf 合同.pdf`（内置合同要素抽取）
  - `--fields my_fields.json`（自定义字段，走 core2 动态抽取）
  - `--dry-run`（只解析+切窗，不调 LLM，用于验证环境）
  - `--output out.json`
- `.env.example` —— 配置模板（智谱/DeepSeek/OpenAI/Ollama 四种示例）

### 修改
- `utils/get_formdoc.py`、`utils/get_react.py`、`core2/input_processor.py`：`from contractlib import form_doc` → `from extractor_pdf.document_parsing import form_doc`
- `utils/label_info_builder.py`：pb2 → `proto_like`
- `core/position_processor.py`：pb2 `Rect` → 本地 `Rect`
- `core/extractor.py`：`MessageToJson` → `dataclass序列化`
- `utils/llm.py`：删除内网专用路由分支，仅保留通用 OpenAI 兼容路径；key/URL/模型全部走 `.env`
- `config/settings.py`：删除 gRPC/OCR 配置和硬编码公司默认值；缺 key 时不再启动即崩，而是调用 LLM 时才报错
- `utils/direct_parser.py`：gRPC 远程解析 → 本地 `parse_file()`（保留函数名，签名不变）
- `requirements.txt`：去掉 git+ssh 依赖，新增 `pymupdf`
- `README.md`：重写为个人版使用说明

### 删除（仅工作区删除，git 历史保留）
- `serv.py`（gRPC 服务入口）、`api/service.py`、`api/client.py`（gRPC 调试客户端）
- `Jenkinsfile`、`deployments/`、`.tinker.yaml`、`.hooks/`（企业 CI）
- `textract` 依赖（编译麻烦，老 `.doc` 二进制格式不再支持，README 说明转换方法）

### 保留不动
- `core/`、`core2/` 抽取流水线全部逻辑、prompts（`prompts.json` / `items_prompts.json`）
- `function_call/`、`get_relations/`（无内部依赖的可选增强）
- `Dockerfile`、样例合同文件

## 4. 个人版使用方式（预览）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 LLM（复制模板后填入你自己的 key）
cp .env.example .env

# 3. 抽取一份合同（内置要素：主体/金额/时间/交易主体/基本信息）
python -m extractor_pdf "合同.pdf" -o result.json

# 4. 自定义字段抽取
python -m extractor_pdf "合同.docx" --fields my_fields.json -o result.json

# 5. 环境自检（不调用 LLM）
python -m extractor_pdf "合同.pdf" --dry-run

# Python API
from extractor_pdf import extractor, extractor_with_dynamic_fields
from extractor_pdf.document_parsing import new_formdoc_from_path
formdoc = new_formdoc_from_path("合同.pdf")
result = await extractor(formdoc)   # asyncio
```

## 5. 顺带修复的企业版遗留 Bug

1. **`core/extract_items.py` 缩进事故**：`_extract` 及 `extract_subject/extract_amout/...`
   系列方法因缩进错位落在了类体之外（模块级函数带 `self`），`Extractor` 类实际没有这些
   方法，core 流水线一启动就 `AttributeError`。已将其归还类内，逻辑未动。
2. **`models/extraction_result.py` 缺字段**：core2 的 `extract_fields_from_window` 给
   `ExtractionResult.position_info` 赋值，但模型未声明该字段（pydantic 拒绝），动态字段
   链路必然失败。已补 `position_info: Optional[Dict] = None`。

## 6. 验证结果（2026-10-25）

- `test_local_parsing.py`：样例 PDF（27页/649段/6表格/6窗口）与 DOCX（99段/2表格）解析、
  切窗全通过；PDF 字符框与文本严格等长（0 处不一致）。
- `test_mock_e2e.py`：Mock LLM 下 core 全链路（抽取→合并→快速定位→字符矩形→FormRes JSON）
  通过，"合同编号"定位到第 0 页段落 4，坐标真实有效。
- core2 动态字段链路（Mock）通过：自定义字段"合同名称"抽取成功。
- `python -m extractor_pdf <pdf> --dry-run` 正常。
- 真实 LLM 调用需在 `.env` 配置 key 后使用（本机当时无可用 key，未实测）。

## 7. 已知取舍

1. **扫描版 PDF（纯图片无文本层）**：PyMuPDF 只解析文本层，不带 OCR。需要 OCR 的场景可后续接入 PaddleOCR/RapidOCR（占位说明见 README）。
2. **DOCX 版面坐标**：Word 格式本身不含渲染坐标，个人版对 DOCX 提供段落级定位（pos_id）+ 伪页码，不提供字符级矩形。PDF 仍是完整字符级定位。
3. **`.doc` 老格式**：不再支持（原版依赖的 textract 本来也装不上）。请先用 Word/WPS 另存为 `.docx`。
4. **gRPC 服务**：个人场景无跨系统集成需求，移除。若以后需要，`enterprise-v2-archive` tag 里有完整实现可参考。
