import os
from extractor_pdf.utils.decorators import singleton
import json
import re

@singleton
class GetRelations:
    def __init__(self):
        self.relations = self.load_relations()

    def load_relations(self, file_path: str = './relations.json'):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        absolute_path = os.path.join(current_dir, os.path.basename(file_path))
        with open(absolute_path, 'r', encoding='utf-8') as file:
            return json.load(file)
        
    def get_relations(self, name: str):
        name = name.replace('（','(').replace('）',')')
        # print(f'name >>> {name}')
        return self.relations.get(name, None)
    
    # TODO: 需要添加一个方法来update这个relations


get_relations = GetRelations()

if __name__ == '__main__':
    print(get_relations.load_relations())