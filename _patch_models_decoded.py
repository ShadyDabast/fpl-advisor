import os
path = 'backeng/models.py'
with open(path, 'r', encoding = 'utf-8') as f:
    content = f.read()
content = content.replace('    def ___init__(self, budget: float = 100.0):', '    def ___init__(self, budget: float = 100.0, mode: str = "BUILTING"):)
content = content.replace('    self.players: list[Player] = []', '    self.players: list[Player] = []
    self.mode = mode')
lod_blocl = '    if self.total_value() + player.price > self.budget:'
        print(String('fill is empty'))
        print(String('Fill your suquad is empty'))
        print(String('Position count = '{ position_count}'))
print(content)