import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib
import sys

def main():
    webview = WebKit2.WebView()
    webview.load_uri("https://example.com")
    
    def on_load_changed(wv, event):
        print("Load event:", event)
        if event == WebKit2.LoadEvent.FINISHED:
            print("Loaded without window!")
            sys.exit(0)
            
    webview.connect("load-changed", on_load_changed)
    GLib.timeout_add(5000, lambda: sys.exit(1))
    Gtk.main()

if __name__ == "__main__":
    main()
