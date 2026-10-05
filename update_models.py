import os  
path = 'backend/models.py'  
with open(path, 'r', encoding='utf-8') as f:  
    content = f.read()  
content = content.replace('    def __init__(self, budget: float = 100.0):', '    def __init__(self, budget: float = 100.0, mode: str = \" "BUILDING\):')  
content = content.replace('        self.players: list[Player] = []', '        self.players: list[Player] = []\n        self.mode = mode')  
content = content.replace('            \budget\: self.budget,', '            \budget\: self.budget,\n            \mode\: self.mode,')  
with open(path, 'w', encoding='utf-8') as f:  
    f.write(content)  
print('updated') 
