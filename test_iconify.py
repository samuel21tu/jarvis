import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib
import sys

def main():
    window = Gtk.Window()
    webview = WebKit2.WebView()
    webview.load_html("<script>setInterval(() => { document.title = 'TICK ' + Date.now(); }, 1000);</script>", "http://localhost")
    window.add(webview)
    window.show_all()
    
    ticks = 0
    def loop_check():
        nonlocal ticks
        print("Title:", webview.get_title())
        ticks += 1
        
        if ticks == 2:
            print("Iconifying...")
            window.iconify()
            
        if ticks == 5:
            print("Deiconifying...")
            window.deiconify()
            
        if ticks > 6:
            sys.exit(0)
            
        return True

    GLib.timeout_add(1500, loop_check)
    Gtk.main()

if __name__ == "__main__":
    main()
