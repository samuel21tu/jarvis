import re

with open('src/mobile/styles.css', 'r') as f:
    content = f.read()

# Add the collapsed rules before the last closing brace of the media query
insertion = """
    /* Modo Recolhido (Mobile Collapsed) */
    .hud-main-workspace.mobile-collapsed .hud-left-column,
    .hud-main-workspace.mobile-collapsed .activity-log-box,
    .hud-main-workspace.mobile-collapsed .file-upload-box,
    .hud-main-workspace.mobile-collapsed .command-input-box {
        display: none !important;
    }

    .hud-main-workspace.mobile-collapsed {
        justify-content: center;
        align-items: center;
    }

    .hud-main-workspace.mobile-collapsed .hud-center-column {
        flex: 1;
        justify-content: center;
        max-height: 100%;
        margin-top: 10vh; /* Centraliza a esfera verticalmente */
    }
"""

if "mobile-collapsed" not in content:
    pos = content.rfind("}")
    if pos != -1:
        new_content = content[:pos] + insertion + content[pos:]
        with open('src/mobile/styles.css', 'w') as f:
            f.write(new_content)
        print("CSS alterado com sucesso.")
    else:
        print("Não achou final.")
else:
    print("Já alterado.")
