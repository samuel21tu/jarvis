import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib
import sys

def main():
    window = Gtk.Window()
    window.set_default_size(400, 800)
    
    webview = WebKit2.WebView()
    webview.load_html("<html><body style='background:red;'><h1>Hello</h1></body></html>", "http://localhost")
    
    def on_load_changed(wv, event):
        if event == WebKit2.LoadEvent.FINISHED:
            print("Loaded!")
            
    webview.connect("load-changed", on_load_changed)
    
    # We do NOT add it to the window yet
    window.realize()
    
    def toggle():
        nonlocal window, webview
        if webview.get_parent() is not None:
            print("Hiding")
            window.remove(webview)
            window.hide()
        else:
            print("Showing")
            window.add(webview)
            window.show_all()
            window.present()
        return True

    GLib.timeout_add(2000, toggle)
    GLib.timeout_add(8000, lambda: sys.exit(0))
    Gtk.main()

if __name__ == "__main__":
    main()
