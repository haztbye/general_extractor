"""个人版命令行入口。

用法:
    # 内置合同要素抽取（主体/金额/时间/基本信息/交易主体）
    python -m extractor_pdf 合同.pdf -o result.json

    # 自定义字段抽取（core2 动态字段）
    python -m extractor_pdf 合同.docx --fields my_fields.json -o result.json

    # 环境自检：只解析 + 切窗，不调用 LLM
    python -m extractor_pdf 合同.pdf --dry-run
"""

import argparse
import asyncio
import json
import os
import sys

from loguru import logger


def _load_field_configs(fields_path: str):
    """从 JSON 文件加载字段配置。格式:
    [{"field_name": "合同名称", "field_type": 0, "field_description": "...", "extraction_example": "..."}]
    """
    from extractor_pdf.models.field_config import FieldConfig

    with open(fields_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    configs = []
    for item in raw:
        configs.append(FieldConfig(
            field_name=item["field_name"],
            field_type=item.get("field_type", 0),
            field_description=item.get("field_description") or item.get("description"),
            extraction_example=item.get("extraction_example") or item.get("example"),
        ))
    return configs


def _dry_run(formdoc) -> None:
    """解析 + 切窗自检，不调用 LLM。"""
    from extractor_pdf.utils.get_formdoc import PDFWindowProcessor
    from extractor_pdf.core.window_processor import process_window_text

    processor = PDFWindowProcessor(doc=formdoc)
    windows = processor.process() or []
    print(f"\n[自检] 窗口数量: {len(windows)}")
    total_chars = 0
    for i, wd in enumerate(windows, 1):
        text = process_window_text(wd)
        total_chars += len(text)
        preview = text[:120].replace("\n", " ")
        print(f"  窗口{i}: {len(wd)} 行, {len(text)} 字符 | 预览: {preview}...")
    print(f"[自检] 全部窗口共 {total_chars} 字符。解析与切窗正常。\n")


async def _run_extract(formdoc, field_configs):
    if field_configs:
        from extractor_pdf.core.extractor import extractor_with_dynamic_fields
        return await extractor_with_dynamic_fields(formdoc, field_configs)

    from extractor_pdf.core.extractor import extractor
    from extractor_pdf.proto_like import form_res_to_dict
    form_res = await extractor(formdoc)
    if form_res is None:
        raise RuntimeError(
            "抽取流程返回空结果，请查看上方日志（常见原因：LLM key 未配置或接口不可达）"
        )
    return form_res_to_dict(form_res)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m extractor_pdf",
        description="合同要素抽取（个人版）：PDF/DOCX -> 结构化 JSON",
    )
    parser.add_argument("file", help="待抽取的 .pdf / .docx 文件路径")
    parser.add_argument("--fields", default=None,
                        help="自定义字段配置 JSON 文件（不传则使用内置合同要素）")
    parser.add_argument("-o", "--output", default=None, help="结果输出 JSON 路径（默认打印到终端）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只做解析与窗口切分自检，不调用 LLM")
    parser.add_argument("--window-size", type=int, default=6, help="每个窗口的页数（默认6）")
    parser.add_argument("--overlap", type=int, default=1, help="窗口重叠页数（默认1）")
    args = parser.parse_args(argv)

    if not os.path.exists(args.file):
        print(f"错误: 文件不存在: {args.file}", file=sys.stderr)
        return 2

    # 解析文档（本地，无需网络）
    from extractor_pdf.document_parsing import new_formdoc_from_path
    try:
        formdoc = new_formdoc_from_path(args.file)
    except Exception as e:  # noqa: BLE001
        logger.error(f"文档解析失败: {e}")
        return 1

    if args.dry_run:
        _dry_run(formdoc)
        return 0

    # LLM 配置检查（提前给出清晰提示）
    from extractor_pdf.config.settings import check_llm_ready
    if not check_llm_ready():
        return 2

    field_configs = None
    if args.fields:
        try:
            field_configs = _load_field_configs(args.fields)
        except Exception as e:  # noqa: BLE001
            print(f"错误: 字段配置文件加载失败: {e}", file=sys.stderr)
            return 2

    try:
        result = asyncio.run(_run_extract(formdoc, field_configs))
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        return 130
    except Exception as e:  # noqa: BLE001
        logger.error(f"抽取失败: {e}")
        return 1

    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"结果已写入: {os.path.abspath(args.output)}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
