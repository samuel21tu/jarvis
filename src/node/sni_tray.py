"""
Tray nativo via D-Bus (protocolo StatusNotifierItem + com.canonical.dbusmenu).

Motivo: dentro do Flatpak em sessão Wayland não há DISPLAY X11, então o backend
GTK do pystray (Gtk.StatusIcon / XEmbed) não consegue exibir ícone nem menu.
O protocolo SNI funciona nativamente no KDE Plasma (Wayland e X11) e em GNOME
com a extensão AppIndicator, usando apenas Gio (PyGObject), sem libappindicator.
"""
import os
import threading
import warnings

from gi.repository import Gio, GLib

SNI_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"
WATCHER_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="ContextMenu"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="Activate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="SecondaryActivate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="Scroll"><arg name="delta" type="i" direction="in"/><arg name="orientation" type="s" direction="in"/></method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus"><arg name="status" type="s"/></signal>
  </interface>
</node>
"""

MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/>
      <arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/>
      <arg type="(ia{sv}av)" name="layout" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="a(ia{sv})" name="properties" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/>
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg type="a(isvu)" name="events" direction="in"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" name="id" direction="in"/>
      <arg type="b" name="needUpdate" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="ai" name="updatesNeeded" direction="out"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg type="a(ia{sv})" name="updatedProps"/>
      <arg type="a(ia{sv})" name="removedProps"/>
    </signal>
    <signal name="LayoutUpdated">
      <arg type="u" name="revision"/>
      <arg type="i" name="parent"/>
    </signal>
    <signal name="ItemActivationRequested">
      <arg type="i" name="id"/>
      <arg type="u" name="timestamp"/>
    </signal>
  </interface>
</node>
"""


def _pil_to_argb(image):
    """Converte uma imagem PIL para o formato ARGB32 (big-endian) exigido pelo SNI."""
    img = image.convert("RGBA")
    try:
        data = img.tobytes("raw", "ARGB")
    except Exception:
        # Fallback manual caso o packer ARGB não exista nesta versão do Pillow
        raw = img.tobytes()
        buf = bytearray(len(raw))
        buf[0::4] = raw[3::4]
        buf[1::4] = raw[0::4]
        buf[2::4] = raw[1::4]
        buf[3::4] = raw[2::4]
        data = bytes(buf)
    return img.width, img.height, data


class SNITray:
    """
    Ícone de bandeja SNI com menu dbusmenu.

    items: lista de tuplas (label, callback). Use label=None para separador.
    on_activate: callback do clique esquerdo no ícone (opcional).
    """

    def __init__(self, app_id, title, image, items, on_activate=None):
        self.app_id = app_id
        self.title = title
        self.icon_w, self.icon_h, self.icon_data = _pil_to_argb(image)
        self.on_activate = on_activate
        self.revision = 1
        self.menu = {}  # id -> (props dict de GLib.Variant, callback)
        for idx, (label, cb) in enumerate(items, start=1):
            if label is None:
                props = {"type": GLib.Variant("s", "separator")}
            else:
                props = {
                    "label": GLib.Variant("s", label),
                    "enabled": GLib.Variant("b", True),
                    "visible": GLib.Variant("b", True),
                }
            self.menu[idx] = (props, cb)

        self.conn = None
        self.loop = None
        self._reg_ids = []
        self._watch_id = 0
        self.registered = False

    # ------------------------------------------------------------------ util
    def _run_cb(self, cb):
        """Executa callbacks em thread separada para nunca travar o main loop D-Bus."""
        if not cb:
            return

        def _safe():
            try:
                cb()
            except Exception as e:
                print(f"[TRAY] Erro no callback do menu: {e}")

        threading.Thread(target=_safe, daemon=True).start()

    def _item_variant(self, item_id):
        props, _ = self.menu[item_id]
        return GLib.Variant("(ia{sv}av)", (item_id, props, []))

    def _root_layout(self):
        root_props = {"children-display": GLib.Variant("s", "submenu")}
        children = [self._item_variant(i) for i in sorted(self.menu)]
        return (0, root_props, children)

    # ------------------------------------------------------- SNI handlers
    def _sni_method(self, conn, sender, path, iface, method, params, invocation):
        try:
            if method == "Activate" and self.on_activate:
                self._run_cb(self.on_activate)
            # ContextMenu/SecondaryActivate/Scroll: o menu é servido via dbusmenu
            invocation.return_value(None)
        except Exception as e:
            print(f"[TRAY] Erro em método SNI {method}: {e}")
            invocation.return_value(None)

    def _sni_prop(self, conn, sender, path, iface, prop):
        values = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", self.app_id),
            "Title": GLib.Variant("s", self.title),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconName": GLib.Variant("s", ""),
            "IconPixmap": GLib.Variant("a(iiay)", [(self.icon_w, self.icon_h, self.icon_data)]),
            "AttentionIconName": GLib.Variant("s", ""),
            "ToolTip": GLib.Variant("(sa(iiay)ss)", ("", [], self.title, "")),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", MENU_PATH),
        }
        return values.get(prop)

    # --------------------------------------------------- dbusmenu handlers
    def _menu_method(self, conn, sender, path, iface, method, params, invocation):
        try:
            if method == "GetLayout":
                parent_id = params.unpack()[0]
                if parent_id in self.menu:
                    props, _ = self.menu[parent_id]
                    layout = (parent_id, props, [])
                else:
                    layout = self._root_layout()
                invocation.return_value(GLib.Variant("(u(ia{sv}av))", (self.revision, layout)))
            elif method == "GetGroupProperties":
                ids = params.unpack()[0] or sorted(self.menu)
                result = [(i, self.menu[i][0]) for i in ids if i in self.menu]
                invocation.return_value(GLib.Variant("(a(ia{sv}))", (result,)))
            elif method == "GetProperty":
                item_id, name = params.unpack()
                props = self.menu.get(item_id, ({}, None))[0]
                value = props.get(name, GLib.Variant("s", ""))
                invocation.return_value(GLib.Variant("(v)", (value,)))
            elif method == "Event":
                item_id, event_id = params[0], params[1]
                if event_id == "clicked" and item_id in self.menu:
                    self._run_cb(self.menu[item_id][1])
                invocation.return_value(None)
            elif method == "EventGroup":
                events = params[0]
                for ev in events:
                    item_id, event_id = ev[0], ev[1]
                    if event_id == "clicked" and item_id in self.menu:
                        self._run_cb(self.menu[item_id][1])
                invocation.return_value(GLib.Variant("(ai)", ([],)))
            elif method == "AboutToShow":
                invocation.return_value(GLib.Variant("(b)", (False,)))
            elif method == "AboutToShowGroup":
                invocation.return_value(GLib.Variant("(aiai)", ([], [])))
            else:
                invocation.return_value(None)
        except Exception as e:
            print(f"[TRAY] Erro em método dbusmenu {method}: {e}")
            try:
                invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(e))
            except Exception:
                pass

    def _menu_prop(self, conn, sender, path, iface, prop):
        values = {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }
        return values.get(prop)

    # ------------------------------------------------------- registro
    def _register_with_watcher(self, *_args):
        """Registra o item no StatusNotifierWatcher (chamado também quando o Plasma reinicia)."""
        try:
            self.conn.call_sync(
                WATCHER_NAME, WATCHER_PATH, WATCHER_NAME,
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (self.conn.get_unique_name(),)),
                None, Gio.DBusCallFlags.NONE, 5000, None,
            )
            self.registered = True
            print("[TRAY] Ícone registrado no StatusNotifierWatcher.")
        except Exception as e:
            self.registered = False
            print(f"[TRAY] Falha ao registrar no StatusNotifierWatcher: {e}")

    def _on_watcher_vanished(self, *_args):
        self.registered = False
        print("[TRAY] StatusNotifierWatcher indisponível. Aguardando reaparecer...")

    def start(self):
        """Exporta os objetos D-Bus e inicia a observação do watcher. Lança exceção em falha."""
        self.conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)

        sni_info = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
        menu_info = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]

        # register_object com callables Python é marcado como deprecated em PyGObject recente,
        # mas continua sendo a forma mais portátil entre versões do runtime
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            self._reg_ids.append(self.conn.register_object(
                SNI_PATH, sni_info, self._sni_method, self._sni_prop, None))
            self._reg_ids.append(self.conn.register_object(
                MENU_PATH, menu_info, self._menu_method, self._menu_prop, None))

        # Observa o watcher: registra ao aparecer e re-registra se o painel reiniciar
        self._watch_id = Gio.bus_watch_name_on_connection(
            self.conn, WATCHER_NAME, Gio.BusNameWatcherFlags.NONE,
            self._register_with_watcher, self._on_watcher_vanished,
        )

    def run(self, setup=None):
        """Inicia o tray e bloqueia no GLib.MainLoop."""
        self.start()
        if setup:
            GLib.idle_add(lambda: (setup(), False)[1])
        self.loop = GLib.MainLoop()
        self.loop.run()

    def stop(self):
        try:
            if self._watch_id:
                Gio.bus_unwatch_name(self._watch_id)
            for rid in self._reg_ids:
                self.conn.unregister_object(rid)
        except Exception:
            pass
        if self.loop:
            self.loop.quit()


if __name__ == "__main__":
    # Teste manual isolado: python3 sni_tray.py
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    ImageDraw.Draw(img).ellipse((16, 16, 48, 48), fill="#00f3ff")
    tray = SNITray(
        "jarvis-test", "JARVIS TESTE", img,
        [("Item A", lambda: print("A clicado")), (None, None), ("Sair", lambda: os._exit(0))],
        on_activate=lambda: print("Clique esquerdo"),
    )
    tray.run()
