"""DIY Stream Deck (Arduino Mega) - host program for Windows.

Reads "KEY:n" lines from the Arduino and runs the actions defined in config.json.
K1..K11 = actions of the active profile, K12 = next profile.
Runs in the background with a system tray icon - the letter on the icon is the active profile.
The color of the active profile is sent to the RGB LED on the device.

  python streamdeck.py          normal mode (tray icon)
  python streamdeck.py --test   only prints pressed keys, runs nothing
"""
import json
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent
CFG_PATH = BASE / "config.json"
LOG_PATH = BASE / "streamdeck.log"
IS_WIN = sys.platform == "win32"
TEST = "--test" in sys.argv

handlers = [logging.FileHandler(LOG_PATH, encoding="utf-8")]
if sys.stdout:  # pythonw has no console
    handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S", handlers=handlers)
log = logging.getLogger("deck")

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.02
except Exception as e:
    pyautogui = None
    log.warning(f"pyautogui unavailable ({e}) - keyboard shortcuts will not work")

cfg: dict = {}
state = {"profile": 0, "connected": False, "port": None, "ser": None}
ser_lock = threading.Lock()

ACCENTS = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def to_display(text: str, limit: int = 21) -> str:
    """The device only accepts ASCII; strip Polish diacritics and cut to the line length."""
    return text.translate(ACCENTS).encode("ascii", "ignore").decode()[:limit]


def send(line: str):
    with ser_lock:
        s = state["ser"]
        if s is None:
            return
        try:
            s.write((line + "\n").encode("ascii", "ignore"))
        except Exception:
            pass


def send_profile():
    """Send the RGB LED color of the active profile ("color" in config.json) to the Arduino."""
    prof = cfg["profiles"][state["profile"]]
    hexc = str(prof.get("color", "#FFFFFF")).lstrip("#")
    try:
        r, g, b = int(hexc[0:2], 16), int(hexc[2:4], 16), int(hexc[4:6], 16)
    except ValueError:
        r = g = b = 255
    send(f"C:{r},{g},{b}")
    send("P:" + to_display(prof["name"], 16))


tray = None  # pystray icon (if available)


def load_config():
    global cfg
    try:
        new = json.loads(CFG_PATH.read_text(encoding="utf-8"))
        assert new.get("profiles"), "no profiles defined"
        cfg = new
        state["profile"] %= len(cfg["profiles"])
        log.info(f"config loaded: {', '.join(p['name'] for p in cfg['profiles'])}")
        return True
    except Exception as e:
        log.error(f"error in config.json: {e}")
        notify("Error in config.json", str(e))
        return False


# ---------------------------------------------------------------- actions

def focus_window(title: str):
    try:
        import pygetwindow as gw
        wins = [w for w in gw.getAllWindows() if title.lower() in w.title.lower()]
        if wins:
            w = wins[0]
            if w.isMinimized:
                w.restore()
            w.activate()
            time.sleep(0.15)
        else:
            log.info(f"  (window '{title}' not found)")
    except Exception as e:
        log.info(f"  focus: {e}")


def run_action(a: dict):
    t = a.get("type")
    if a.get("focus"):
        focus_window(a["focus"])
    if t in ("hotkey", "key", "type") and pyautogui is None:
        return
    if t == "hotkey":
        pyautogui.hotkey(*a["keys"])
    elif t == "key":
        pyautogui.press(a["key"])
    elif t == "type":
        pyautogui.write(a["text"], interval=0.01)
    elif t == "open":
        target = os.path.expandvars(a["target"])
        os.startfile(target) if IS_WIN else webbrowser.open(target)
    elif t == "launch":
        subprocess.Popen(os.path.expandvars(a["cmd"]), shell=True)
    elif t == "shell":
        cwd = os.path.expandvars(a["cwd"]) if a.get("cwd") else None
        cmd = f'start "" cmd /k "{a["cmd"]}"' if IS_WIN else a["cmd"]
        subprocess.Popen(cmd, shell=True, cwd=cwd)
    elif t == "wait":
        time.sleep(float(a.get("seconds", 0.5)))
    elif t == "sequence":
        for step in a["steps"]:
            run_action(step)
            time.sleep(float(a.get("delay", 0.1)))
    else:
        log.warning(f"  unknown action type: {t}")


def press(n: int):
    profile = cfg["profiles"][state["profile"]]
    keys = profile["keys"]
    if not 1 <= n <= len(keys):
        log.info(f"K{n}: no action in profile {profile['name']}")
        return
    k = keys[n - 1]
    log.info(f"K{n}: {profile['name']} → {k['label']}")
    send("A:" + to_display(k["label"]))
    if TEST:
        return

    def worker():
        try:
            run_action(k["action"])
        except Exception as e:
            log.error(f"  '{k['label']}' - error: {e}")
    threading.Thread(target=worker, daemon=True).start()


def next_profile():
    state["profile"] = (state["profile"] + 1) % len(cfg["profiles"])
    name = cfg["profiles"][state["profile"]]["name"]
    log.info(f"K{cfg.get('profile_key', 12)}: profile → {name}")
    send_profile()
    refresh_tray()
    if cfg.get("notify_on_profile_change", True):
        notify(f"Profile: {name}", "")


def handle_line(line: str):
    if not line.startswith("KEY:"):
        return
    try:
        n = int(line[4:])
    except ValueError:
        return
    if n == int(cfg.get("profile_key", 12)):
        next_profile()
    else:
        press(n)


# ---------------------------------------------------------------- Arduino

def find_port():
    from serial.tools import list_ports
    for p in list_ports.comports():
        d = f"{p.description} {p.manufacturer or ''}".lower()
        if any(s in d for s in ("arduino", "mega", "ch340", "ch341", "usb serial")):
            return p.device
    return None


def set_connected(ok: bool, port=None):
    if state["connected"] != ok:
        state["connected"], state["port"] = ok, port
        refresh_tray()
        if ok:
            log.info(f"Arduino connected ({port})")
        else:
            log.info("Arduino disconnected - waiting…")


def serial_loop():
    import serial
    log.info("looking for Arduino…")
    while True:
        port = cfg.get("serial_port") or "auto"
        if port == "auto":
            port = find_port()
        if not port:
            set_connected(False)
            time.sleep(3)
            continue
        try:
            with serial.Serial(port, int(cfg.get("baud", 115200)), timeout=1) as s:
                time.sleep(2)  # the Arduino resets when the port is opened
                s.reset_input_buffer()
                with ser_lock:
                    state["ser"] = s
                set_connected(True, port)
                send_profile()
                while True:
                    handle_line(s.readline().decode(errors="ignore").strip())
        except Exception as e:
            with ser_lock:
                state["ser"] = None
            if state["connected"]:
                log.info(f"port {port}: {e}")
            set_connected(False)
            time.sleep(3)


def heartbeat():
    """Re-send the profile every 5 s - this is the heartbeat that tells the Arduino the host is alive."""
    while True:
        time.sleep(5)
        if state["connected"]:
            send_profile()


# ---------------------------------------------------------------- tray icon

def make_icon_image(letter: str, ok: bool):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, 62, 62], radius=14, fill=(79, 140, 255) if ok else (110, 110, 120))
    try:
        font = ImageFont.truetype("arialbd.ttf", 40)
    except OSError:
        font = ImageFont.load_default(size=40)
    d.text((32, 33), letter, fill="white", font=font, anchor="mm")
    return img


def notify(title: str, msg: str):
    if tray is not None:
        try:
            tray.notify(msg or " ", title)
        except Exception:
            pass


def refresh_tray():
    if tray is None:
        return
    name = cfg["profiles"][state["profile"]]["name"]
    tray.icon = make_icon_image(name[:1].upper(), state["connected"])
    conn = f"connected ({state['port']})" if state["connected"] else "no Arduino"
    tray.title = f"Stream Deck - {name}\n{conn}"
    try:
        tray.update_menu()
    except Exception:
        pass


def build_menu():
    import pystray
    from pystray import MenuItem as Item

    def select(i):
        def _(icon, item):
            state["profile"] = i
            send_profile()
            refresh_tray()
        return _

    profiles = [Item(p["name"], select(i), checked=(lambda i: lambda item: state["profile"] == i)(i), radio=True)
                for i, p in enumerate(cfg["profiles"])]

    def reload_cfg(icon, item):
        if load_config():
            icon.menu = build_menu()
            send_profile()
            refresh_tray()
            notify("Config reloaded", "")

    return pystray.Menu(
        *profiles,
        pystray.Menu.SEPARATOR,
        Item("Edit config.json", lambda i, it: os.startfile(CFG_PATH) if IS_WIN else None),
        Item("Reload config", reload_cfg),
        Item("Show log", lambda i, it: os.startfile(LOG_PATH) if IS_WIN else None),
        pystray.Menu.SEPARATOR,
        Item("Quit", lambda icon, item: icon.stop()),
    )


def main():
    global tray
    if not load_config():
        sys.exit(1)
    if TEST:
        log.info("TEST MODE - actions will not be executed")
    threading.Thread(target=serial_loop, daemon=True).start()
    threading.Thread(target=heartbeat, daemon=True).start()
    try:
        import pystray
        name = cfg["profiles"][state["profile"]]["name"]
        tray = pystray.Icon("streamdeck", make_icon_image(name[:1].upper(), False), "Stream Deck", build_menu())
        refresh_tray()
        tray.run()
    except ImportError:
        log.info("pystray missing - running without a tray icon, Ctrl+C to quit")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
