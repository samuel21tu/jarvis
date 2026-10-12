import re

with open('src/mobile/app.js', 'r') as f:
    content = f.read()

# Substituir o final onde adiciona eventos ao btnFullscreen
target_str = """
btnFullscreen.addEventListener('click', toggleFullscreen);
btnF11Link.addEventListener('click', toggleFullscreen);
"""

replacement_str = """
if (isMobileDevice) {
    mainWorkspace.classList.add('mobile-collapsed');
    btnFullscreen.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
        <path d="M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z"></path>
    </svg>`;
    btnFullscreen.title = "Expandir/Recolher Painéis";
    
    btnFullscreen.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        mainWorkspace.classList.toggle('mobile-collapsed');
    });
} else {
    btnFullscreen.addEventListener('click', toggleFullscreen);
}
btnF11Link.addEventListener('click', toggleFullscreen);
"""

if target_str.strip() in content:
    content = content.replace(target_str.strip(), replacement_str.strip())
    with open('src/mobile/app.js', 'w') as f:
        f.write(content)
    print("JS alterado com sucesso.")
else:
    print("Alvo não encontrado no JS.")
