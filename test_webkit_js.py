import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib
import sys

def main():
    webview = WebKit2.WebView()
    webview.load_html("<script>setInterval(() => { console.log('TICK'); document.title = 'TICK ' + Date.now(); }, 1000);</script>", "http://localhost")
    
    ticks = 0
    def check_title():
        nonlocal ticks
        print("Title:", webview.get_title())
        ticks += 1
        if ticks > 3:
            sys.exit(0)
        return True

    GLib.timeout_add(1500, check_title)
    Gtk.main()

if __name__ == "__main__":
    main()
