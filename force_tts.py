import sys

with open("src/mobile/app.js", "r") as f:
    content = f.read()

target = "if (allVoices.length === 0) {"
replacement = "if (true || allVoices.length === 0) {"

if target in content:
    content = content.replace(target, replacement)
    with open("src/mobile/app.js", "w") as f:
        f.write(content)
    print("Patch applied.")
else:
    print("Target not found.")
