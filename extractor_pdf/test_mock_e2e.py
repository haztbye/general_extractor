"""Mock LLM 全链路测试：不依赖真实 key，验证 core 流水线端到端编排。

流程：解析 PDF -> 窗口切分 -> (Mock)LLM 抽取 -> 合并 -> 快速定位 -> 字符矩形计算 -> FormRes
运行: python extractor_pdf/test_mock_e2e.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

PDF = "examples/sample_contract.pdf"

# 从示例文档中取的子串作为 mock 抽取值，保证快速定位路径可命中
MOCK_FIELD_VALUE = "SZ-DEMO-2026-001"


async def mock_llm_response_async(prompt: str = '', **kwargs) -> str:
    """模拟 LLM：抽取类 prompt 返回固定 JSON；定位类 prompt 返回空结果。"""
    await asyncio.sleep(0)
    if "段落位置" in prompt:  # locate_text prompt
        return "```json\n{}\n```"
    body = {"合同编号": MOCK_FIELD_VALUE, "甲方名称": "示例制造有限公司"}
    return f"```json\n{json.dumps(body, ensure_ascii=False)}\n```"


async def main():
    # 注入 mock（patch 两个导入点）
    import extractor_pdf.core.extract_items as ei
    import extractor_pdf.core.locator_optimized as lo
    ei.get_llm_response_async = mock_llm_response_async
    lo.get_llm_response_async = mock_llm_response_async

    from extractor_pdf.document_parsing import new_formdoc_from_path
    from extractor_pdf.core.extractor import extractor
    from extractor_pdf.proto_like import form_res_to_dict

    formdoc = new_formdoc_from_path(PDF)
    form_res = await extractor(formdoc)
    assert form_res is not None, "extractor 返回 None（流水线报错，见日志）"

    data = form_res_to_dict(form_res)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1500])

    labels = data["labels"]
    assert labels, "结果为空"

    hit = 0
    for key, val in labels.items():
        for info in val["labels"]:
            if info["value"]:
                hit += 1
    assert hit > 0, "没有抽取到任何值"

    # 验证定位矩形（合同编号应命中字符级矩形）
    contract_no = labels.get("合同编号", {}).get("labels", [])
    if contract_no:
        pos_list = contract_no[0]["pos"]
        assert pos_list, "合同编号无定位"
        r = pos_list[0]["rect"]
        print(f"\n定位验证: 合同编号 -> 段落 {pos_list[0]['coordinates']}, "
              f"{len(r)} 个矩形, 首个矩形页码 {r[0]['page_id']}, 坐标 {r[0]['coord']}")
    print("\nMock 全链路测试通过 ✅（真实 LLM 只需在 .env 配置 key 即可）")


if __name__ == "__main__":
    asyncio.run(main())
