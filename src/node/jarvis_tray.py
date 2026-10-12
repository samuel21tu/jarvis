import os
import sys
import threading
import subprocess
import time

from PIL import Image, ImageDraw

def create_image(width, height, color1, color2):
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.ellipse((width // 4, height // 4, width * 3 // 4, height * 3 // 4), fill=color2)
    return image

def run_cmd(cmd_list):
    if os.path.exists("/.flatpak-info"):
        return ["flatpak-spawn", "--host"] + cmd_list
    return cmd_list

def notify(title, msg):
    try:
        subprocess.Popen(run_cmd(["notify-send", title, msg]))
    except Exception:
        pass

def toggle_microphone(*_args):
    try:
        subprocess.run(run_cmd(["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "toggle"]), check=True)
        # Tenta pegar o status
        res = subprocess.run(run_cmd(["pactl", "get-source-mute", "@DEFAULT_SOURCE@"]), capture_output=True, text=True)
        state = "Mutado" if "yes" in res.stdout.lower() or "sim" in res.stdout.lower() else "Desmutado (Ouvindo)"
        notify("Jarvis Mic", f"Estado atual: {state}")
    except Exception as e:
        print(f"Erro ao mutar microfone: {e}")

chrome_process = None
chrome_lock = threading.Lock()

# Perfil isolado para a instância única do JARVIS no Chrome
CHROME_PROFILE = "/tmp/jarvis_chrome_profile"
CHROME_MATCH = r"chrome.*--user-data-dir=/tmp/[j]arvis_chrome_profile"

def _chrome_running():
    try:
        res = subprocess.run(run_cmd(["pgrep", "-f", CHROME_MATCH]), capture_output=True, text=True, timeout=5)
        return res.returncode == 0
    except Exception:
        return False

def kill_chrome(timeout=6.0):
    global chrome_process
    try:
        if chrome_process and chrome_process.poll() is None:
            try:
                chrome_process.terminate()
            except Exception:
                pass

        subprocess.run(run_cmd(["pkill", "-TERM", "-f", CHROME_MATCH]), check=False, timeout=5)

        deadline = time.time() + timeout
        while time.time() < deadline and _chrome_running():
            time.sleep(0.25)

        if _chrome_running():
            print("[CHROME] Forçando SIGKILL...")
            subprocess.run(run_cmd(["pkill", "-KILL", "-f", CHROME_MATCH]), check=False, timeout=5)
            time.sleep(0.5)

        if chrome_process:
            try:
                chrome_process.wait(timeout=2)
            except Exception:
                pass

        stale = [f"{CHROME_PROFILE}/SingletonLock", f"{CHROME_PROFILE}/SingletonSocket", f"{CHROME_PROFILE}/SingletonCookie"]
        subprocess.run(run_cmd(["rm", "-f"] + stale), check=False, timeout=5)
    except Exception as e:
        print(f"[CHROME] Aviso ao encerrar: {e}")

def setup_tray():
    icon_path = os.path.join(os.path.dirname(__file__), "..", "mobile", "favicon.jpg")
    if os.path.exists(icon_path):
        try:
            icon_image = Image.open(icon_path)
        except Exception:
            icon_image = create_image(64, 64, 'black', '#00f3ff')
    else:
        icon_image = create_image(64, 64, 'black', '#00f3ff')

    try:
        setup_tray_sni(icon_image)
    except Exception as e:
        print(f"[TRAY] SNI indisponível ({e}). Usando fallback pystray...")
        setup_tray_pystray(icon_image)

def launch_chrome():
    """Lança ou foca a janela do JARVIS sem reiniciar a sessão do navegador nem cortar o áudio."""
    global chrome_process

    with chrome_lock:
        url = os.getenv("JARVIS_WEB_URL", "https://jarvis.samuel21tu.space/")
        cmd = [
            "google-chrome-stable",
            f"--user-data-dir={CHROME_PROFILE}",
            "--no-first-run",
            "--no-default-browser-check",
            "--test-type",
            "--disable-infobars",
            "--hide-crash-restore-bubble",
            "--disable-session-crashed-bubble",
            "--use-fake-ui-for-media-stream",
            "--autoplay-policy=no-user-gesture-required",
            f"--app={url}"
        ]

        if _chrome_running():
            print("[CHROME] Instância já ativa. Solicitando foco da janela...")
            try:
                # Dispara a chamada do Chrome IPC: o processo principal existente recebe e foca a janela
                subprocess.Popen(run_cmd(cmd))
                return
            except Exception as e:
                print(f"[CHROME] Erro ao focar janela existente: {e}")

        print(f"[CHROME] Lançando nova instância: {' '.join(cmd)}")
        try:
            chrome_process = subprocess.Popen(run_cmd(cmd))
        except Exception as e:
            chrome_process = None
            print(f"[CHROME] Erro ao lançar Chrome: {e}")
            notify("JARVIS", f"Falha ao abrir o Chrome: {e}")

def toggle_app(*_args):
    """Ação do menu/ícone de bandeja: foca o painel sem interromper a fala ou escuta."""
    threading.Thread(target=launch_chrome, daemon=True).start()

_tray_ref = {"icon": None}

def exit_action(*_args):
    global chrome_process
    if chrome_process:
        try:
            chrome_process.kill()
        except Exception:
            pass
    kill_chrome(timeout=3.0)
    icon = _tray_ref.get("icon")
    if icon:
        try:
            icon.stop()
        except Exception:
            pass
    os._exit(0)

def setup(icon=None):
    if icon is not None and hasattr(icon, "visible"):
        icon.visible = True
    threading.Thread(target=launch_chrome, daemon=True).start()


def setup_tray_sni(icon_image):
    """Tray nativo SNI via D-Bus (funciona em Wayland dentro do Flatpak)."""
    from sni_tray import SNITray

    tray = SNITray(
        "jarvis-node",
        "JARVIS PC Node",
        icon_image,
        [
            ("Abrir / Fechar Painel", toggle_app),
            ("Mutar/Desmutar Microfone", toggle_microphone),
            (None, None),
            ("Sair", exit_action),
        ],
        on_activate=toggle_app,  # Clique esquerdo no ícone também abre/fecha o painel
    )
    _tray_ref["icon"] = tray
    tray.run(setup=setup)

def setup_tray_pystray(icon_image):
    """Fallback legado com pystray (precisa de X11/AppIndicator)."""
    os.environ.setdefault("PYSTRAY_BACKEND", "gtk")
    import pystray

    menu = pystray.Menu(
        pystray.MenuItem("Abrir / Fechar Painel", toggle_app, default=True),
        pystray.MenuItem("Mutar/Desmutar Microfone", toggle_microphone),
        pystray.MenuItem("Sair", exit_action)
    )

    icon = pystray.Icon("JARVIS", icon_image, "JARVIS PC Node", menu)
    _tray_ref["icon"] = icon
    icon.run(setup=setup)

def setup_tray():
    icon_path = os.path.join(os.path.dirname(__file__), "..", "mobile", "favicon.jpg")
    if os.path.exists(icon_path):
        try:
            icon_image = Image.open(icon_path)
        except Exception:
            icon_image = create_image(64, 64, 'black', '#00f3ff')
    else:
        icon_image = create_image(64, 64, 'black', '#00f3ff')

    try:
        setup_tray_sni(icon_image)
    except Exception as e:
        print(f"[TRAY] SNI indisponível ({e}). Usando fallback pystray...")
        setup_tray_pystray(icon_image)


if __name__ == "__main__":
    # Garante que os módulos irmãos (jarvis_node, sni_tray) sejam importáveis
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import jarvis_node
    import asyncio

    def run_node_thread():
        while True:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(jarvis_node.run_node())
            except Exception as e:
                print(f"[NODE] Erro no nó, reiniciando em 5s: {e}")
            time.sleep(5)

    node_thread = threading.Thread(target=run_node_thread, daemon=True)
    node_thread.start()

    setup_tray()
