# general-extract-v2（个人版）

从 PDF / DOCX 合同中抽取结构化要素（主体、金额、时间、交易主体、基本信息等），
并定位到文档版面位置（段落 id + 字符级矩形坐标）。

> 本项目为**个人可独立运行**的重构版本：不依赖任何内部服务，解析全部本地完成，
> LLM 走任意 OpenAI 兼容接口。从早期服务版到本地版的改造对照见 [MIGRATION.md](MIGRATION.md)。

## 快速开始

```bash
# 1. 安装依赖（Python 3.10+）
pip install -r requirements.txt

# 2. 配置你自己的 LLM（任选智谱/DeepSeek/OpenAI/Ollama）
cp .env.example .env
# 编辑 .env，填入 LLM_SERVICE_API_KEY

# 3. 抽取（内置合同要素，仓库自带一份合成示例合同可立即体验）
python -m extractor_pdf examples/sample_contract.pdf -o result.json

# 4. 自定义字段抽取
python -m extractor_pdf 你的合同.pdf --fields examples/fields_example.json -o result.json

# 5. 环境自检（只解析+切窗，不调用 LLM、不需要 key）
python -m extractor_pdf 任意合同.pdf --dry-run
```

## 输出格式

内置要素抽取（core 流水线）输出 JSON：

```json
{
  "labels": {
    "含税金额": {
      "labels": [
        {
          "value": "1280000",
          "type": "含税金额",
          "meta": {"extract_data": "..."},
          "pos": [
            {
              "coordinates": "42",
              "rect": [{"coord": [[95.0, 612.3], [186.2, 612.3], [186.2, 624.1], [95.0, 624.1]], "page_id": 0}]
            }
          ]
        }
      ]
    }
  }
}
```

- `coordinates`：命中段落的 id（与切窗时的 pos_id 对应）
- `rect`：字段文本的字符级矩形（四点坐标 + 页码，PDF 有效；DOCX 为段落级伪坐标）

## Python API

```python
import asyncio
from extractor_pdf import extractor, extractor_with_dynamic_fields, FieldConfig, FieldType
from extractor_pdf.document_parsing import new_formdoc_from_path

formdoc = new_formdoc_from_path("合同.pdf")

# 内置要素
result = asyncio.run(extractor(formdoc))

# 自定义字段
fields = [FieldConfig(field_name="违约金比例", field_type=FieldType.TEXT, field_description="...")]
result = asyncio.run(extractor_with_dynamic_fields(formdoc, fields))
```

## 项目结构（个人版）

```
extractor_pdf/
├── cli.py / __main__.py     # 命令行入口
├── document_parsing/        # 本地文档解析（替代 contractlib + 内部OCR/parser服务）
│   ├── models.py            #   FormDoc/Section/Table/Rect 数据模型
│   ├── form_doc.py          #   兼容 API: formdoc_iter/get_section_text/is_table...
│   ├── pdf_parser.py        #   PyMuPDF 解析 PDF（字符坐标+表格）
│   └── docx_parser.py       #   python-docx 解析 DOCX
├── proto_like.py            # FormRes 等返回结构的本地等价（替代 protobuf）
├── core/                    # 第一版流水线：切窗→抽取→定位→坐标→合并
├── core2/                   # 动态字段抽取（字段配置驱动）
├── utils/                   # LLM 客户端 / Prompt 管理 / JSON 容错解析
├── config/settings.py       # 配置（.env 驱动）
└── test_local_parsing.py    # 本地解析链路自检
```

## 支持与限制

| 场景 | 支持情况 |
|---|---|
| 文本层 PDF（含 Word 导出的 PDF） | ✅ 字符级定位 |
| DOCX | ✅ 段落级定位（伪页码，无字符坐标） |
| 扫描件 PDF（纯图片） | ❌ 暂不带 OCR，请先用 OCR 工具转成带文本层的 PDF |
| 老版 .doc | ❌ 请先用 Word/WPS 另存为 .docx |

## 常见问题

- **报"未配置 LLM_SERVICE_API_KEY"**：在项目根目录建 `.env`（模板 `.env.example`），或设置同名环境变量。
- **JSON 解析报错**：LLM 偶发返回非严格 JSON，`json_processor` 会自动纠错；若频繁出现可换更稳的模型或降低 temperature。
- **字段定位为空**：跨行/复杂版式的字段会回退到段落级定位，属正常行为。
- **想看窗口切分效果**：`python -m extractor_pdf 文件 --dry-run`。
