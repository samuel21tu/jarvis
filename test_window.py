import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib
import sys

def main():
    window = Gtk.Window()
    window.set_default_size(400, 800)
    window.set_opacity(0.0)
    window.move(-10000, -10000)
    window.show_all()
    print("Initial position:", window.get_position())

    def show_later():
        window.set_opacity(1.0)
        window.set_position(Gtk.WindowPosition.CENTER)
        window.present()
        print("After present:", window.get_position())
        sys.exit(0)

    GLib.timeout_add(1000, show_later)
    Gtk.main()

if __name__ == "__main__":
    main()
