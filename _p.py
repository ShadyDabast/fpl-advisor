import os  
path = 'backend/models.py'  
c = open(path, 'r', encoding='utf-8').read()  
c = c.replace('    def __init__(self, budget: float = 100.0):', '    def __init__(self, budget: float = 100.0, mode: str = \" "BUILDING\):')  
c = c.replace('        self.players: list[Player] = []', '        self.players: list[Player] = []\n        self.mode = mode')  
open(path, 'w', encoding='utf-8').write(c)  
print('done')  
