from typing import List
from extractor_pdf.models.document import ExtractResult

def merge_results(results: List[ExtractResult]) -> dict:
    all_extract_result = {}
    # name_counters = {}
    for r in results:
        name = r.item_name
        text = r.text
        
        if name not in all_extract_result or text and not all_extract_result[name].text:
            all_extract_result[name] = r
            # name_counters[name] = 0
        # else:
        #     if text != all_extract_result[name] and text != '':
        #         name_counters[name] += 1
        #         new_name = f"{name}_{name_counters[name]}"
        #         all_extract_result[new_name] = r
    return all_extract_result