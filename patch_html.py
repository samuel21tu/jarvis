with open('src/mobile/index.html', 'r') as f:
    c = f.read()
c = c.replace('v=20261009_v7', 'v=20261009_v8')
with open('src/mobile/index.html', 'w') as f:
    f.write(c)
print("HTML atualizado")
