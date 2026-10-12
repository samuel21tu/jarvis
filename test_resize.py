import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib
import sys

def main():
    window = Gtk.Window()
    window.set_default_size(400, 800)
    window.show_all()
    
    ticks = 0
    def loop_check():
        nonlocal ticks
        print("Size:", window.get_size())
        ticks += 1
        
        if ticks == 2:
            print("Resizing to 1x1...")
            window.resize(1, 1)
            
        if ticks == 5:
            print("Resizing to 400x800...")
            window.resize(400, 800)
            
        if ticks > 6:
            sys.exit(0)
            
        return True

    GLib.timeout_add(1500, loop_check)
    Gtk.main()

if __name__ == "__main__":
    main()
