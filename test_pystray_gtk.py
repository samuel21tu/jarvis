import os
os.environ["PYSTRAY_BACKEND"] = "gtk"
import pystray
from PIL import Image, ImageDraw

def setup(icon):
    icon.visible = True
    # Test importing Gtk
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    print("GTK works")
    icon.stop()

image = Image.new('RGB', (64, 64), 'black')
icon = pystray.Icon("test", image, menu=pystray.Menu())
icon.run(setup=setup)
