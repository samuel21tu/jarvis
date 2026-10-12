import re

with open('src/mobile/app.js', 'r') as f:
    content = f.read()

# Add URL parameter check at the end of the file, after initWebSocket() and renderHoloCore()
autostart_logic = """

// =============================================================================
// AUTOSTART LOGIC
// =============================================================================
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('autostart') === '1') {
    console.log("[JARVIS DEBUG] Autostart solicitado via URL parameter.");
    setTimeout(() => {
        handleMicToggle(); // Simula o clique no botão para iniciar escuta e desbloquear áudio
    }, 1500);
}
"""

if "AUTOSTART LOGIC" not in content:
    with open('src/mobile/app.js', 'a') as f:
        f.write(autostart_logic)

