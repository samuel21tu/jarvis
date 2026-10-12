import subprocess
def open_native_app():
    url = "http://localhost:8080"
    browsers = ["google-chrome", "chromium", "brave", "microsoft-edge", "vivaldi"]
    for b in browsers:
        try:
            # We must use flatpak-spawn --host to run host browser
            subprocess.run(["flatpak-spawn", "--host", b, f"--app={url}"], check=True)
            return
        except Exception:
            continue
    
    # Fallback
    subprocess.run(["flatpak-spawn", "--host", "xdg-open", url])
open_native_app()
