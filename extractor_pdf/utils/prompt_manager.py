import json
import os
from extractor_pdf.utils.decorators import singleton
from loguru import logger
from extractor_pdf.errors.error_manager import ExtractError

@singleton
class PromptManager:    
    def __init__(self):
        self.load_prompts()
        self.load_items_prompt()

    def load_prompts(self, file_path: str = './prompts.json'):
        # 获取当前脚本文件的目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构建 prompts.json 的绝对路径
        absolute_path = os.path.join(current_dir, os.path.basename(file_path))
        
        try:
            with open(absolute_path, 'r', encoding='utf-8') as file:
                self.prompts = json.load(file)
        except FileNotFoundError:
            print(f"{absolute_path} 文件未找到。")
            self.prompts = {}

    def get_prompt(self, key):
        return self.prompts.get(key)
    
    def load_items_prompt(self, file_path: str = './items_prompts.json'):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        absolute_path = os.path.join(current_dir, os.path.basename(file_path))
        try:
            with open(absolute_path, 'r', encoding='utf-8') as file:
                self.items_prompts = json.load(file)
        except FileNotFoundError:
            print(f"{absolute_path} 文件未找到。")
            self.items_prompts = {}
    
    def get_items_prompt(self ,classify: str, key: str = ''):
        if not classify:
            raise ExtractError("没说明这个“抽取要素”属于哪个类")
        if not key:
            return self.items_prompts.get(classify)
        return self.items_prompts.get(classify).get(key)

prompt_manager = PromptManager()

if __name__ == "__main__":
    content = '''一审：服务费不含税金额人民币9000元，税率为6%，其中,A项目32000元,B项目58000元。
二审:服务费含税金额人民币45000元,不含税金额42452.83元,税率6%。
其中,A项目16000元,B项目29000元。若二审未发生,不了支付二审服务费。'''
    prompt = prompt_manager.get_prompt("get_formula").format(target="含税总金额", content=content)
    print(prompt)
    items_prompt = prompt_manager.get_items_prompt("合同基本信息")
    print(items_prompt)

    print('-'*40)
    ###### 测试单例的装饰器是否生效
    def test_singleton():
        # 创建两个实例
        manager1 = PromptManager()
        manager2 = PromptManager()
        
        # 打印对象的内存地址
        print(f"manager1的ID: {id(manager1)}")
        print(f"manager2的ID: {id(manager2)}")
        
        # 判断是否是同一个对象
        print(f"是否是同一个对象: {manager1 is manager2}")
        
        # 修改第一个实例的属性，看第二个实例是否同步变化
        manager1.test_attr = "测试属性"
        print(f"manager2是否有相同属性: {hasattr(manager2, 'test_attr')}")
        print(f"manager2的属性值: {getattr(manager2, 'test_attr', None)}")
    
    test_singleton()