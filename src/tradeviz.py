"""
Trade Visualizer for EU4
Created on 21 aug. 2013

@author: Jeroen Kools
"""

# TODO: Show countries option: ALL, specific tag
# TODO: Improve map readability at lower resolutions? (e.g. 1280x720)
# TODO: Full, tested support for Mac and Linux
# TODO: Nodes show options: Player abs trade power, player rel trade power, total trade power

# DEPENDENCIES:
# PyParsing: http://pyparsing.wikispaces.com or use 'pip install pyparsing'
# Python Imaging Library: http://www.pythonware.com/products/pil/
# On Ubuntu: aptitude install python-tk python-imaging python-imaging-tk python-pyparsing

# standard lib stuff
import json
import logging
import os
import platform
import re
import sys
import threading
import time
# GUI stuff
import tkinter as tk
import tkinter.filedialog as tk_file_dialog
import tkinter.messagebox as tk_message_box
import types
import zipfile
from distutils import version
from math import sqrt, ceil, log1p
from tkinter import ttk

# Third party libs
import pyparsing
import tkmacosx
from PIL import Image, ImageTk, ImageDraw

# Tradeviz components
import src.NodeGrammar as NodeGrammar
from src.TradeGrammar import trade_section

# Globals
provinceBMP = "../res/worldmap.gif"
WinRegKey = "SOFTWARE\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Steam App 236850"  # Win64 only...
MacDefaultPath = os.path.expanduser("~/Library/Application Support/Steam/Steamapps/common/Europa Universalis IV")
LinuxDefaultPath = os.path.expanduser("~/.local/share/Steam/SteamApps/common/Europa Universalis IV")

# Colors
LIGHT_SLATE = "#36434b"
DARK_SLATE = "#29343a"
BTN_BG = "#364555"
BANNER_BG = "#9E9186"
WHITE = "#fff"
YELLOW = "#ff0"
RED = "#d00"
PURPLE = "#90c"
BLACK = "#000"

# Fonts
SMALL_FONT = ("Cambria", 12)
BIG_FONT = ("Cambria", 18, "bold")

VERSION = "1.5.0"
COMPATIBILITY_VERSION = version.LooseVersion("1.21.1")  # EU4 version
APP_NAME = "EU4 Trade Visualizer"


class TradeViz:
    """Main class for Europa Universalis Trade Visualizer"""

    def __init__(self):
        logging.basicConfig(handlers=[logging.StreamHandler(), logging.FileHandler("tradeviz.log", mode="w")],
                            level=debug_level, format="[%(asctime)s] %(levelname)s: %(message)s",
                            datefmt="%Y/%m/%d %H:%M:%S")
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing application on %s, Python %s", platform.platform(), platform.python_version())

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.wm_attributes('-fullscreen', 'true')

        self.paneHeight = 195
        self.w, self.h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.title("%s v%s" % (APP_NAME, VERSION))
        self.root.bind("<Escape>", lambda x: self.exit("Esc key pressed"))
        self.root.wm_protocol("WM_DELETE_WINDOW", lambda: self.exit("Window closed"))
        self.zeroArrows = []

        try:
            self.root.iconbitmap(r"../res/merchant.ico")
        except Exception as e:
            self.logger.error("Error setting application icon (expected on Unix): %s" % e)

        try:
            self.mapImg = Image.open(provinceBMP).convert("RGB")
            self.mapWidth = self.mapImg.size[0]
            self.mapHeight = self.mapImg.size[1]
            self.mapImg.thumbnail((self.w - 10, self.h), Image.BICUBIC)
            self.draw_img = self.mapImg.convert("RGB")
            self.mapThumbSize = self.mapImg.size
            self.ratio = self.mapThumbSize[0] / float(self.mapWidth)
            self.provinceImage = ImageTk.PhotoImage(self.mapImg)
        except Exception as e:
            self.logger.critical("Error preparing the world map!\n%s" % e)

        self.logger.debug("Setting up GUI")
        self.gui = types.SimpleNamespace()
        self.setup_gui()
        self.tradenodes = []
        self.player = ""
        self.date = ""
        self.zoomed = False
        self.done = False
        self.saveVersion = ""
        self.preTradeSectionLines = 0
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(7, weight=1)
        self.config = {}
        self.get_config()
        self.root.deiconify()
        self.logger.debug("Entering main loop")
        self.root.mainloop()

    def get_config(self):
        """Retrieve settings from config file"""

        self.logger.debug("Getting config")

        if os.path.exists(r"../tradeviz.cfg"):
            with open(r"../tradeviz.cfg") as f:
                self.config = json.load(f)

        if "savefile" in self.config:
            self.gui.saveEntry.insert(0, self.config["savefile"])
        if "showZeroRoutes" in self.config:
            self.gui.showZeroVar.set(self.config["showZeroRoutes"])
        if "nodesShow" in self.config:
            self.gui.nodesShowVar.set(self.config["nodesShow"])
        if "lastModPath" in self.config:
            self.gui.modPathVar.set(self.config["lastModPath"])
        if "modPaths" in self.config:
            self.gui.modPathComboBox.configure(values=[""] + self.config["modPaths"])
        if "arrowScale" in self.config:
            self.gui.arrowScaleVar.set(self.config["arrowScale"])

        defaults = {"savefile": "", "showZeroRoutes": 0, "nodesShow": "Total value",
                    "modPaths": [], "lastModPath": "", "arrowScale": "Square root"}

        for k in defaults:
            if k not in self.config:
                self.config[k] = defaults[k]

        if "installDir" not in self.config or not os.path.exists(self.config["installDir"]):
            self.get_install_dir()

        self.save_config()

    def save_config(self):
        """Store settings in config file"""

        self.logger.debug("Saving config")

        with open(r"../tradeviz.cfg", "w") as f:
            json.dump(self.config, f)

    def get_install_dir(self):
        """Find the EU4 install path and store it in the config for later use"""

        self.logger.debug("Getting install dir")

        if sys.platform == "win32":
            import _winreg
            try:
                key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, WinRegKey)
                i = 0
                while 1:
                    quoted_name, val, _type = _winreg.EnumValue(key, i)
                    if quoted_name == "InstallLocation":
                        self.logger.info("Found install dir in Windows registry: %s" % val)
                        self.config["installDir"] = val
                        break
                    i += 1

            except WindowsError as e:
                self.logger.error("Error while trying to find install dir in Windows registry: %s" % e)

        elif sys.platform == "darwin":  # OS X

            if os.path.exists(MacDefaultPath):
                self.config["installDir"] = MacDefaultPath

        else:  # Assume it's Linux
            if os.path.exists(LinuxDefaultPath):
                self.config["installDir"] = LinuxDefaultPath

        if "installDir" not in self.config:
            self.config["installDir"] = ""

        if self.config["installDir"] == "" or not os.path.exists(self.config["installDir"]):
            self.show_error("EU4 installation folder not found!",
                            "Europa Universalis 4 installation could not be found! " +
                            "The program needs to read some files from the game to work correctly. " +
                            "Please select your installation folder manually.")
            folder = tk_file_dialog.askdirectory(initialdir="/")
            if os.path.exists(os.path.join(folder, "common")):
                self.config["installDir"] = folder

    def setup_gui(self):
        """Initialize the user interface elements"""

        self.gui.canvas = tk.Canvas(self.root, width=self.mapThumbSize[0], height=self.mapThumbSize[1],
                                    highlightthickness=0, border=5, relief="flat", bg=DARK_SLATE)
        self.gui.canvas.grid(row=1, column=0, columnspan=4, sticky="W", padx=5)
        self.gui.canvas.bind("<Button-1>", self.click_map)
        TradeViz.setup_tk_styles()
        self.root.option_add("*TCombobox*Listbox*Background", DARK_SLATE)
        self.root.option_add("*TCombobox*Listbox*Foreground", WHITE)
        self.root.option_add("*TCombobox*Listbox*selectBackground", LIGHT_SLATE)
        self.root.option_add("*TCombobox*Listbox*selectForeground", WHITE)
        self.root.geometry("%dx%d+0+0" % (self.w, self.h))
        self.root.minsize(self.w, self.h - 20)
        self.root.maxsize(self.w, self.h - 20)
        self.root.wm_state('zoomed')
        self.root.configure(background=DARK_SLATE)

        # Labels, entries, checkboxes

        tk.Label(self.root, text="EU4 Trade Visualizer", bg=BANNER_BG, fg=WHITE, font=BIG_FONT).grid(
            row=0, column=0, columnspan=4, sticky="WE", padx=10, pady=(10, 5))

        tk.Label(self.root, text="Save file:", bg=DARK_SLATE, fg=WHITE,
                 font=SMALL_FONT, anchor="w").grid(row=2, column=0, padx=6, pady=2, sticky="WE")

        self.gui.saveEntry = ttk.Entry(self.root)
        self.gui.saveEntry.grid(row=2, column=1, columnspan=2, sticky="WE", padx=6, pady=4, ipady=0)

        tk.Label(self.root, text="Mod:", bg=DARK_SLATE, fg=WHITE,
                 font=SMALL_FONT).grid(row=3, column=0, padx=(6, 2), pady=2, sticky="W")
        self.gui.modPathVar = tk.StringVar()
        self.gui.modPathComboBox = ttk.Combobox(self.root, textvariable=self.gui.modPathVar, values=[""],
                                                state="readonly",
                                                font=SMALL_FONT)
        self.gui.modPathComboBox.grid(row=3, column=1, columnspan=2, sticky="WE", padx=6, pady=2)
        self.gui.modPathVar.trace("w", self.mod_path_changed)

        tk.Label(self.root, text="Nodes show:", bg=DARK_SLATE, fg=WHITE, font=SMALL_FONT).grid(row=4, column=0,
                                                                                               padx=(6, 2), pady=2,
                                                                                               sticky="W")
        self.gui.nodesShowVar = tk.StringVar()
        self.gui.nodesShowVar.set("Total value")
        self.gui.nodesShow = ttk.Combobox(self.root, textvariable=self.gui.nodesShowVar,
                                          values=["Local value", "Total value"],
                                          state="readonly", font=SMALL_FONT)
        self.gui.nodesShow.grid(row=4, column=1, columnspan=2, sticky="W", padx=6, pady=2)
        self.gui.nodesShowVar.trace("w", self.nodes_show_changed)

        tk.Label(self.root, text="Arrow scaling:", bg=DARK_SLATE, fg=WHITE, font=SMALL_FONT).grid(row=5, column=0,
                                                                                                  padx=(6, 2), pady=2,
                                                                                                  sticky="W")
        self.gui.arrowScaleVar = tk.StringVar()
        self.gui.arrowScaleVar.set("Square root")
        self.gui.arrowScale = ttk.Combobox(self.root, textvariable=self.gui.arrowScaleVar,
                                           values=["Linear", "Square root", "Logarithmic"],
                                           state="readonly", font=SMALL_FONT)
        self.gui.arrowScale.grid(row=5, column=1, columnspan=2, sticky="W", padx=6, pady=2)
        self.gui.arrowScaleVar.trace("w", self.arrow_scale_changed)

        self.gui.showZeroVar = tk.IntVar(value=1)
        self.gui.show_zeroes = ttk.Checkbutton(self.root, text="Show unused trade routes",
                                               variable=self.gui.showZeroVar, command=self.toggle_show_zeroes)
        self.gui.show_zeroes.grid(row=6, column=0, columnspan=2, sticky="W", padx=6, pady=2)

        # Buttons

        self.gui.browse_file_button = tkmacosx.Button(self.root, text="Browse...", command=self.browse_save,
                                                      bg=BTN_BG, fg=WHITE, font=SMALL_FONT, relief="ridge")
        self.gui.browse_file_button.grid(row=2, column=3, sticky="nswe", padx=7, pady=3)

        self.gui.browse_mod_folder_button = tkmacosx.Button(self.root, text="Browse...", command=self.browse_mod,
                                                            bg=BTN_BG, fg=WHITE, font=SMALL_FONT, relief="ridge")
        self.gui.browse_mod_folder_button.grid(row=3, column=3, sticky="nswe", padx=7, pady=3, ipady=1)

        self.gui.go_button = tkmacosx.Button(self.root, text="Go!", command=self.go, bg=BTN_BG, fg=WHITE,
                                             font=SMALL_FONT + ("bold",), relief="ridge")
        self.gui.go_button.grid(row=7, column=1, sticky="SE", ipadx=20, padx=7, pady=15)

        self.gui.save_image_button = tkmacosx.Button(self.root, text="Save Map", command=self.save_map,
                                                     bg=BTN_BG, fg=WHITE, font=SMALL_FONT, relief="ridge")
        self.gui.save_image_button.grid(row=7, column=2, sticky="SE", padx=7, pady=15)

        self.gui.exit_button = tkmacosx.Button(self.root, text="Exit", command=lambda: self.exit("Exit button pressed"),
                                               bg=BTN_BG, fg=WHITE, font=SMALL_FONT, relief="ridge")
        self.gui.exit_button.grid(row=7, column=3, sticky="SWE", padx=7, pady=15)

    @staticmethod
    def setup_tk_styles():
        style = ttk.Style()
        style.theme_create(
            'tradeviz_style',
            parent='alt',
            settings={'TCombobox': {
                'configure':
                    {'selectforeground': WHITE,
                     'selectbackground': LIGHT_SLATE,
                     'fieldforeground': WHITE,
                     'fieldbackground': LIGHT_SLATE,
                     'foreground': WHITE,
                     'background': DARK_SLATE,
                     }
            },
                'TListbox': {
                    "configure":
                        {'selectforeground': WHITE,
                         'selectbackground': LIGHT_SLATE,
                         'fieldforeground': WHITE,
                         'fieldbackground': LIGHT_SLATE,
                         'foreground': WHITE,
                         'background': DARK_SLATE,
                         }
                },
                'TCheckbutton': {
                    "configure":
                        {
                            'indicatorcolor': LIGHT_SLATE,
                            'foreground': WHITE,
                            'background': DARK_SLATE,
                        }
                },
                'TEntry': {
                    "configure":
                        {
                            "fieldforeground": WHITE,
                            "fieldbackground": LIGHT_SLATE,
                            "foreground": WHITE,
                        }
                }
            }
        )
        style.theme_use('tradeviz_style')

    def browse_save(self):
        """Let the user browse for an EU4 save file to be used by the program"""

        self.logger.debug("Browsing for save file")

        initial_dir = "."
        if "savefile" in self.config:
            initial_dir = os.path.dirname(self.config["savefile"])

        filename = tk_file_dialog.askopenfilename(filetypes=[("EU4 Saves", "*.eu4")], initialdir=initial_dir)
        self.logger.info("Selected save file %s" % os.path.basename(filename))
        self.config["savefile"] = filename
        self.save_config()

        self.gui.saveEntry.delete(0, tk.END)
        self.gui.saveEntry.insert(0, self.config["savefile"])

    def browse_mod(self):
        self.logger.debug("Browsing for mod")

        init_dir = "/"
        if self.config["lastModPath"]:
            init_dir = os.path.split(self.config["lastModPath"])[0]
        else:
            for path in self.config["modPaths"]:
                if path:  # not empty
                    init_dir = os.path.basename(path)
                    break

        mod_path = tk_file_dialog.askopenfilename(filetypes=[("EU4 Mods", "*.mod")], initialdir=init_dir)

        self.logger.debug("Selected mod path %s" % mod_path)

        mod_zip = mod_path.replace(".mod", ".zip")
        mod_dir = mod_path.replace(".mod", "")

        if not os.path.exists(mod_zip) and not os.path.exists(mod_dir):
            if mod_path:
                self.show_error("mod_dir %s and mod_zip %s do not appear to be a valid mod" % (mod_dir, mod_zip),
                                "This does not seem to be a valid mod path!")
            return

        self.gui.modPathVar.set(mod_path)
        if mod_path not in self.config["modPaths"]:
            self.config["modPaths"] += [mod_path]

        self.config["lastModPath"] = mod_path

    def go(self):
        """Start parsing the selected save file and show the results on the map"""

        self.logger.info("Processing save file")
        self.done = False
        self.go_time = time.time()
        self.clear_map()
        #wait_icon_thread = threading.Thread(target=self.do_wait_icon)
        #wait_icon_thread.start()

        if self.config["savefile"]:

            try:
                txt = self.get_save_text()
                self.logger.info("Reading save text succeeded")
            except ReadError as e:
                self.show_error("Failed to get savefile text: %s",
                                "This save file caused the following error: %s and can't be processed by %s" %
                                (e.message, e.message, APP_NAME))
                self.draw_map(True)
                return

            try:
                trade_section_txt = txt[1]  # drop part before trade section starts
                trade_section_txt = trade_section_txt.split("production_leader")[0]  # drop the part after the end
                self.get_trade_data(trade_section_txt)
                self.get_node_data()

            except Exception as e:
                msg = "Tradeviz could not parse this file. You might be trying to open a corrupted save," + \
                      "or a save created with an unsupported mod or game version."
                if type(e) == pyparsing.ParseException:
                    e = pyparsing.ParseException(e)
                    print("----------------------------")
                    print(e.line)
                    print(" " * (e.column - 1) + "^")
                    print(e)

                    msg += "Error: " + str(e)
                elif type(e) == IndexError:
                    print(str(e))
                    print("+" + str(self.preTradeSectionLines))

                self.show_error(e, "Can't read file! " + msg)

            try:
                self.draw_map(True)
            except InvalidTradeNodeException as e:
                self.show_error("Invalid trade node index: %s" % e,
                                "Save file contains invalid trade node info. " +
                                "If your save is from a modded game, please indicate the mod folder and try again.")

    def do_wait_icon(self, angle=0):
        # TODO: do this animation using tk.after(), instead of multithreading and time.sleep()...
        my = self.h / 2 - self.paneHeight + 40
        mx = self.w / 2
        radius = 16
        arcs = list()
        arcs.append(
            self.gui.canvas.create_arc(mx - radius, my - radius, mx + radius, my + radius, fill=WHITE, outline=WHITE,
                                       start=angle))
        arcs.append(
            self.gui.canvas.create_arc(mx - radius, my - radius, mx + radius, my + radius, fill=WHITE, outline=WHITE,
                                       start=(angle + 180)))

        while not self.done and (time.time() - self.go_time) < 10:
            self.gui.canvas.itemconfig(arcs[0], start=angle)
            self.gui.canvas.itemconfig(arcs[1], start=angle + 180)

            self.gui.canvas.update_idletasks()
            angle -= 8
            time.sleep(.05)

        for arc in arcs:
            self.gui.canvas.delete(arc)

    def get_save_text(self):
        """Extract the text from the selected save file"""

        self.gui.canvas.create_text((self.mapThumbSize[0] / 2, self.mapThumbSize[1] / 2),
                                    text="Please wait... Save file is being processed...",
                                    fill="white",
                                    font=SMALL_FONT)
        self.logger.debug("Reading save file %s" % os.path.basename(self.config["savefile"]))

        with open(self.config["savefile"], encoding="latin-1", mode="r") as f:
            try:
                txt = f.read()
            except Exception as e:
                print("\a")
                raise ReadError(str(e))

            txt = self.check_for_compression(txt)
            self.check_for_iron_man(txt)
            self.check_for_version(txt)

            if not txt.startswith("EU4txt"):
                self.logger.error("Savefile starts with %s, not EU4txt" % txt[:10])
                raise ReadError("appears to be in an invalid format")

            for line in txt[:2000].split("\n"):
                if "=" in line:
                    key, val = line.split("=")
                    if key == "date":
                        self.date = val.strip('" \n')
                    elif key == "player":
                        self.player = val.strip('" \n')
                    elif key == "speed":
                        break

            txt = txt.split("trade=")
            self.preTradeSectionLines = txt[0].count("\n")

        return txt

    def check_for_iron_man(self, txt):
        self.logger.debug("Checking if save file is IronMan encoded..")
        if txt.startswith("EU4bin"):
            raise ReadError("appears to be an Ironman save")

    def check_for_compression(self, txt):
        """Check whether the save file text is compressed.
        If so, return uncompressed text, otherwise return the text unchanged"""
        if txt[:2] == "PK":
            self.logger.info("Save file is compressed, unzipping...")
            zipped_save = zipfile.ZipFile(self.config["savefile"])
            filename = [x for x in zipped_save.namelist() if x.endswith(".eu4") or x == "gamestate"][0]
            unzipped_save = zipped_save.open(filename)
            txt = unzipped_save.read().decode("latin-1")
            return txt
        else:
            return txt

    def check_for_version(self, txt):
        version_tuple = re.findall("first=(/d+)/s+second=(/d+)/s+third=(/d+)", txt[:500])
        if version_tuple == list():
            self.logger.warning("Could not find version info!")
            self.saveVersion = version.LooseVersion("???")
        else:
            version_tuple = version_tuple[0]
            self.saveVersion = version.LooseVersion("%s.%s.%s" % version_tuple)
            self.logger.info("Save version is %s" % self.saveVersion)
            if self.saveVersion > COMPATIBILITY_VERSION:
                tk_message_box.showwarning(
                    "Version warning",
                    ("This save is from a newer EU4 version (%s) than the version this tool "
                     "officially supports (%s). It might not work correctly!") %
                    (self.saveVersion.vstring, COMPATIBILITY_VERSION.vstring))

    def toggle_show_zeroes(self, *_):
        """Turn the display of trade routes with a value of zero on or off"""

        self.logger.debug("Show zeroes toggled")
        self.config["showZeroRoutes"] = self.gui.showZeroVar.get()

        if not self.zeroArrows and self.gui.showZeroVar.get():
            self.draw_map()
        else:
            for itemId in self.zeroArrows:
                if self.gui.showZeroVar.get():
                    self.gui.canvas.itemconfig(itemId, state="normal")
                else:
                    self.gui.canvas.itemconfig(itemId, state="hidden")

        self.save_config()

    def nodes_show_changed(self, *_):
        self.config["nodesShow"] = self.gui.nodesShowVar.get()
        self.draw_map()

    def arrow_scale_changed(self, *_):
        self.config["arrowScale"] = self.gui.arrowScaleVar.get()
        self.draw_map()

    def mod_path_changed(self, *_):
        self.config["lastModPath"] = self.gui.modPathVar.get()

    def exit(self, reason=""):
        """Close the program"""

        self.save_config()
        self.logger.info("Exiting... (%s)" % reason)
        logging.shutdown()
        self.root.quit()

    def get_trade_data(self, trade_section_txt):
        """Extract the trade data from the selected save file"""

        self.logger.info("Parsing %i chars" % len(trade_section_txt))
        t0 = time.time()

        self.logger.debug("Parsing trade section...")
        result = trade_section.parseString(trade_section_txt)
        result_dict = result.asDict()
        r = {}

        self.logger.info("Finished parsing save in %.3f seconds" % (time.time() - t0))

        self.max_incoming = 0
        self.max_current = 0
        self.max_local = 0

        self.logger.debug("Processing parsed results")

        for node_dict in result_dict["Nodes"]:
            node = {}
            for k in node_dict:
                if k not in ["quotedName", "incomingFromNode", "incomingValue"]:
                    node[k] = node_dict[k]
                elif k in ["incomingFromNode", "incomingValue"]:
                    node[k] = node_dict[k]

                if k == "currentValue":
                    self.max_current = max(self.max_current, node_dict[k])
                if k == "localValue":
                    self.max_local = max(self.max_local, node_dict[k])
                if k == "incomingValue":
                    self.max_incoming = max(self.max_incoming, *node_dict[k])

            r[node_dict["quotedName"][0]] = node

        try:
            self.logger.debug("Seville:\n\t%s" % r["sevilla"])
            self.logger.debug("max current value: %s" % self.max_current)
            self.logger.debug("max incoming value: %s" % self.max_incoming)
        except KeyError:
            self.logger.warning("Trade node Seville not found! Save file is either from a modded game or malformed!")

        self.node_data = r

    def get_node_name(self, node_id):
        node = self.tradenodes[node_id - 1]
        return node[0]

    def get_node_location(self, node_id):
        if node_id > len(self.tradenodes) + 1:
            raise InvalidTradeNodeException(node_id)
        node = self.tradenodes[node_id - 1]
        province_id = node[1]

        for loc in self.province_locations:
            if loc[0] == province_id:
                return loc[1:]

    def get_node_data(self):
        """Retrieve trade node and province information from the game or mod files"""

        self.logger.debug("Getting node data")

        tradenodes = r"common/tradenodes/00_tradenodes.txt"
        positions = r"map/positions.txt"

        mod_path = self.gui.modPathComboBox.get()
        mod_zip = mod_path.replace(".mod", ".zip")
        mod_dir = mod_path.replace(".mod", "")

        mod_type = ""
        if mod_path and os.path.isdir(mod_dir):
            mod_type = "dir"
        elif os.path.exists(mod_zip):
            mod_type = "zip"

        # Get all trade node provinceIDs, modded or default
        try:
            if mod_type == "zip":
                z = zipfile.ZipFile(mod_zip)
                if os.path.normpath(tradenodes) in z.namelist():
                    self.logger.debug("Using tradenodes file from zipped mod")
                    with z.open(tradenodes) as f:
                        txt = f.read()
                else:
                    trade_nodes_file = os.path.join(self.config["installDir"], tradenodes)
                    self.logger.debug("Using default tradenodes file")
                    with open(trade_nodes_file, encoding="latin-1", mode="r") as f:
                        txt = f.read()

            else:
                if mod_type == "dir" and os.path.exists(os.path.join(mod_dir, tradenodes)):
                    trade_nodes_file = os.path.join(mod_dir, tradenodes)
                    self.logger.debug("Using tradenodes file from mod directory")
                else:
                    trade_nodes_file = os.path.join(self.config["installDir"], tradenodes)
                    self.logger.debug("Using default tradenodes file")

                with open(trade_nodes_file, encoding="latin-1", mode="r") as f:
                    txt = f.read()
        except IOError as e:
            self.logger.critical("Could not find trade nodes file: %s" % e)

        txt = remove_comments(txt)
        tradenodes = NodeGrammar.nodes.parseString(txt)
        # for tn in tradenodes: print(tn)
        self.logger.info("%i tradenodes found in %i chars" % (len(tradenodes), len(txt)))

        for i, trade_node in enumerate(tradenodes):
            tradenodes[i] = (trade_node["name"], trade_node["location"])

        self.tradenodes = tradenodes

        # Now get province positions
        try:
            if mod_type == "zip":
                z = zipfile.ZipFile(mod_zip)
                if os.path.normpath(positions) in z.namelist():
                    self.logger.debug("Using positions file from zipped mod")
                    with z.open(positions, mode="r") as f:
                        txt = f.read()
                else:
                    positions_file = os.path.join(self.config["installDir"], positions)
                    self.logger.debug("Using default positions file")

                    with open(positions_file, encoding="latin-1", mode="r") as f:
                        txt = f.read()
            else:
                if mod_type == "dir" and os.path.exists(os.path.join(mod_dir, positions)):
                    positions_file = os.path.join(mod_dir, positions)
                    self.logger.debug("Using positions file from mod directory")
                else:
                    positions_file = os.path.join(self.config["installDir"], positions)
                    self.logger.debug("Using default positions file")

                with open(positions_file, encoding="latin-1", mode="r") as f:
                    txt = f.read()
        except IOError as e:
            self.logger.critical("Could not find locations file: %s" % e)

        locations = re.findall(r"(\d+)=\s*{\s*position=\s*{\s*([\d\.]*)\s*([\d\.]*)", txt)
        for i in range(len(locations)):
            a, b, c = locations[i]

            locations[i] = (int(a), float(b), self.mapHeight - float(c))  # invert y coordinate :)

        self.province_locations = locations
        self.logger.info("Found %i province locations" % len(self.province_locations))

    def get_node_radius(self, node):
        """Calculate the radius for a trade node given its value"""

        if self.config["nodesShow"] == "Total value":
            if "currentValue" in node:
                value = safe_division(node["currentValue"], self.max_current)
            else:
                value = 0
        elif self.config["nodesShow"] == "Local value":
            if "localValue" in node:
                value = safe_division(node["localValue"], self.max_local)
            else:
                value = 0
        else:
            self.logger.error("Invalid nodesShow option: %s" % self.config["nodesShow"])
            value = 0

        return 5 + int(7 * value)

    def get_line_width(self, value):

        arrow_scale_style = self.gui.arrowScaleVar.get()

        if value <= 0:
            return 1

        elif arrow_scale_style == "Linear":
            return int(ceil(safe_division(10 * value, self.max_incoming)))

        elif arrow_scale_style == "Square root":
            return int(round(safe_division(10 * sqrt(value), sqrt(self.max_incoming))))

        elif arrow_scale_style == "Logarithmic":
            return int(round(safe_division(10 * log1p(value), log1p(self.max_incoming))))

    def intersects_node(self, node1, node2):
        """
        Check whether a trade route intersects a trade node circle (other than source and target nodes)
        See http://mathworld.wolfram.com/Circle-LineIntersection.html
        """

        for n, node3 in enumerate(self.tradenodes):
            nx, ny = self.get_node_location(n + 1)
            data = self.node_data[node3[0]]

            r = self.get_node_radius(data) / self.ratio

            # assume circle center is at 0,0
            x2, y2 = self.get_node_location(node1)
            x1, y1 = self.get_node_location(node2)
            x1 -= nx
            y1 -= ny
            x2 -= nx
            y2 -= ny

            if (x1, y1) == (0, 0) or (x2, y2) == (0, 0):
                continue

            D = x1 * y2 - x2 * y1
            dx = x2 - x1
            dy = y2 - y1
            dr = sqrt(dx ** 2 + dy ** 2)
            det = r ** 2 * dr ** 2 - D ** 2

            if det > 0:
                # infinite line intersects, check whether the center node is inside the rectangle
                # defined by the other nodes
                if min(x1, x2) < 0 < max(x1, x2) and min(y1, y2) < 0 < max(y1, y2):
                    self.logger.debug("%s is intersected by a trade route between %s and %s" %
                                      (self.get_node_name(n + 1), self.get_node_name(node1), self.get_node_name(node2)))
                    return True

    def draw_arrow(self, from_node, to_node, value, to_radius):
        """Draw an arrow between two nodes on the map"""

        if value <= 0 and not self.gui.showZeroVar.get():
            return

        x2, y2 = self.get_node_location(from_node)
        x, y = self.get_node_location(to_node)
        is_pacific = self.pacific_trade(x, y, x2, y2)

        # adjust for target node radius
        dx = x - x2
        if is_pacific:
            if x > x2:
                dx = x2 - self.mapWidth - x
            else:
                dx = self.mapWidth - x + x2
        dy = y - y2
        length = max(1.0, sqrt(dx ** 2 + dy ** 2))
        radius_fraction = to_radius / length

        # adjust to stop at node circle's edge
        x -= 3 * dx * radius_fraction
        y -= 3 * dy * radius_fraction

        # rescale to unit length
        dx /= length
        dy /= length

        ratio = self.ratio
        line_width = self.get_line_width(value)
        arrow_shape = (max(8, line_width * 2), max(10.0, line_width * 2.5), max(5, line_width))
        w = max(5 / ratio, 1.5 * line_width / ratio)
        line_color = BLACK if value > 0 else YELLOW

        if not is_pacific:

            center_of_line = ((x + x2) / 2 * ratio, (y + y2) / 2 * ratio)

            if self.intersects_node(from_node, to_node):
                d = 20
                center_of_line = (center_of_line[0] + d, center_of_line[1] + d)
                z1 = self.gui.canvas.create_line((x * ratio, y * ratio, center_of_line[0], center_of_line[1]),
                                                 width=line_width, arrow=tk.FIRST, arrowshape=arrow_shape,
                                                 fill=line_color)
                z2 = self.gui.canvas.create_line((center_of_line[0], center_of_line[1], x2 * ratio, y2 * ratio),
                                                 width=line_width, fill=line_color)

                z3 = self.map_draw.line((x * ratio, y * ratio, center_of_line[0], center_of_line[1]),
                                        width=line_width, fill=line_color)
                z4 = self.map_draw.polygon(
                    (x * ratio, y * ratio,
                     (x - w * dx + w * dy) * ratio, (y - w * dx - w * dy) * ratio,
                     (x - w * dx - w * dy) * ratio, (y + w * dx - w * dy) * ratio
                     ),
                    outline=line_color, fill=line_color)

                z5 = self.map_draw.line((center_of_line[0], center_of_line[1], x2 * ratio, y2 * ratio),
                                        width=line_width, fill=line_color)

                if value == 0:
                    self.zeroArrows += [z1, z2, z3, z4, z5]

            else:
                z1 = self.gui.canvas.create_line((x * ratio, y * ratio, x2 * ratio, y2 * ratio),
                                                 width=line_width, arrow=tk.FIRST, arrowshape=arrow_shape,
                                                 fill=line_color)

                z2 = self.map_draw.line((x * ratio, y * ratio, x2 * ratio, y2 * ratio),
                                        width=line_width, fill=line_color)

                z3 = self.map_draw.polygon(
                    (x * ratio, y * ratio,
                     (x - w * dx + w * dy) * ratio, (y - w * dx - w * dy) * ratio,
                     (x - w * dx - w * dy) * ratio, (y + w * dx - w * dy) * ratio
                     ),
                    outline=line_color, fill=line_color)

                if value == 0:
                    self.zeroArrows += [z1, z2, z3]

            self.gui.arrow_labels.append([center_of_line, value])

        else:  # Trade route crosses edge of map

            if x < x2:  # Asia to America
                z0 = self.gui.canvas.create_line((x * ratio, y * ratio, (-self.mapWidth + x2) * ratio, y2 * ratio),
                                                 width=1, fill=line_color, arrow=tk.FIRST, arrowshape=arrow_shape)
                z1 = self.gui.canvas.create_line(((self.mapWidth + x) * ratio, y * ratio, x2 * ratio, y2 * ratio),
                                                 width=1, fill=line_color, arrow=tk.FIRST, arrowshape=arrow_shape)

                z2 = self.map_draw.line((x * ratio, y * ratio, (-self.mapWidth + x2) * ratio, y2 * ratio),
                                        width=1, fill=line_color)
                z3 = self.map_draw.line(((self.mapWidth + x) * ratio, y * ratio, x2 * ratio, y2 * ratio),
                                        width=1, fill=line_color)
                z4 = self.map_draw.polygon(
                    (x * ratio, y * ratio,
                     (x - w * dx + w * dy) * ratio, (y - w * dx - w * dy) * ratio,
                     (x - w * dx - w * dy) * ratio, (y + w * dx - w * dy) * ratio
                     ),
                    outline=line_color, fill=line_color)

                # fraction of trade route left of "date line"
                f = abs(self.mapWidth - float(x2)) / (self.mapWidth - abs(x - x2))
                # y coordinate where trade route crosses date line
                yf = y2 + f * (y - y2)

                center_of_line = (x / 2 * ratio, (yf + y) / 2 * ratio)
                if value == 0:
                    self.zeroArrows += [z0, z1, z2, z3, z4]

            else:  # Americas to Asia
                z0 = self.gui.canvas.create_line((x * ratio, y * ratio, (self.mapWidth + x2) * ratio, y2 * ratio),
                                                 width=1, fill=line_color, arrow=tk.FIRST, arrowshape=arrow_shape)
                z1 = self.gui.canvas.create_line(((-self.mapWidth + x) * ratio, y * ratio, x2 * ratio, y2 * ratio),
                                                 width=1, fill=line_color, arrow=tk.FIRST, arrowshape=arrow_shape)

                z2 = self.map_draw.line((x * ratio, y * ratio, (self.mapWidth + x2) * ratio, y2 * ratio),
                                        width=1, fill=line_color)
                z3 = self.map_draw.line(((-self.mapWidth + x) * ratio, y * ratio, x2 * ratio, y2 * ratio),
                                        width=1, fill=line_color)
                z4 = self.map_draw.polygon(
                    (x * ratio, y * ratio,
                     (x - w * dx + w * dy) * ratio, (y - w * dx - w * dy) * ratio,
                     (x - w * dx - w * dy) * ratio, (y + w * dx - w * dy) * ratio
                     ),
                    outline=line_color, fill=line_color)

                f = abs(self.mapWidth - float(x)) / (self.mapWidth - abs(x - x2))
                yf = y + f * (y2 - y)

                center_of_line = ((self.mapWidth + x) / 2 * ratio, (yf + y) / 2 * ratio)

            self.gui.arrow_labels.append([center_of_line, value])

            if value == 0:
                self.zeroArrows += [z0, z1, z2, z3, z4]

    def clear_map(self, update=False):
        self.gui.canvas.create_image((0, 0), image=self.provinceImage, anchor=tk.NW)
        self.draw_img = self.mapImg.convert("RGB")
        self.map_draw = ImageDraw.Draw(self.draw_img)
        if update:
            self.gui.canvas.update_idletasks()

    def draw_map(self, clear=False):
        """Top level method for redrawing the world map and trade network"""

        self.logger.debug("Drawing map..")
        t0 = time.time()

        self.logger.debug("Clearing map.. (%s)" % clear)
        self.clear_map(clear)
        self.done = True
        ratio = self.ratio
        self.zeroArrows = []

        self.logger.debug("Cleared map..")

        # draw incoming trade arrows
        t1 = time.time()
        n_arrows = 0
        self.gui.arrow_labels = []

        for n, node in enumerate(self.tradenodes):
            try:
                data = self.node_data[node[0]]

                if "incomingValue" in data:
                    for i, value in enumerate(data["incomingValue"]):
                        from_node_nr = data["incomingFromNode"][i]
                        if from_node_nr >= len(self.tradenodes):
                            continue
                        self.draw_arrow(from_node_nr, n + 1, value, self.get_node_radius(data))
                        n_arrows += 1
                        self.logger.debug("Drew an arrow from %s to %s", from_node_nr, n+1)
            except KeyError:
                self.show_error("Encountered unknown trade node %s!" % node[0],
                                "An invalid trade node was encountered. Save doesn't match" +
                                " currently installed EU4 version, or incorrect mod selected.")
                return
        self.logger.debug("Drew %i arrows in %.2fs" % (n_arrows, time.time() - t1))

        # draw trade arrow labels
        for [centerOfLine, value] in self.gui.arrow_labels:
            if value > 0 or self.gui.showZeroVar.get():
                value_str = "%i" % ceil(value) if (value >= 2 or value <= 0) else ("%.1f" % value)
                z5 = self.gui.canvas.create_text(centerOfLine, text=value_str, fill=WHITE)
                z6 = self.map_draw.text((centerOfLine[0] - 4, centerOfLine[1] - 4), value_str, fill=WHITE)

                if value == 0:
                    self.zeroArrows += [z5, z6]

        # draw trade nodes and their current value
        n_nodes = 0
        for n, node in enumerate(self.tradenodes):
            x, y = self.get_node_location(n + 1)

            if node[0] not in self.node_data:
                self.logger.debug("Node %s not in node data" % node[0])
                continue
            data = self.node_data[node[0]]
            s = self.get_node_radius(data)
            trade_node_color = WHITE

            if self.config["nodesShow"] == "Total value":
                v = data["currentValue"]
                trade_node_color = RED
            elif self.config["nodesShow"] == "Local value":
                v = data["localValue"]
                trade_node_color = PURPLE
            else:
                v = 0

            digits = len("%i" % v)

            self.gui.canvas.create_oval((x * ratio - s, y * ratio - s, x * ratio + s, y * ratio + s),
                                        outline=trade_node_color, fill=trade_node_color)
            self.gui.canvas.create_text((x * ratio, y * ratio), text=int(v), fill="white")

            self.map_draw.ellipse((x * ratio - s, y * ratio - s, x * ratio + s, y * ratio + s),
                                  outline=trade_node_color, fill=trade_node_color)
            self.map_draw.text((x * ratio - 3 * digits, y * ratio - 4), "%d" % v, fill=WHITE)
            n_nodes += 1
        self.logger.debug("Drew %i nodes" % n_nodes)

        self.gui.canvas.create_text((10, self.mapHeight * ratio - 60), anchor="nw",
                                    text="Player: %s" % self.player, fill="white")

        self.gui.canvas.create_text((10, self.mapHeight * ratio - 40), anchor="nw",
                                    text="Date: %s" % self.date, fill="white")

        self.gui.canvas.create_text((10, self.mapHeight * ratio - 20), anchor="nw",
                                    text="Version: %s" % self.saveVersion, fill="white")

        self.map_draw.text((10, self.mapHeight * ratio - 44), "Player: %s" % self.player, fill=WHITE)
        self.map_draw.text((10, self.mapHeight * ratio - 24), "Date: %s" % self.date, fill=WHITE)

        self.logger.info("Finished drawing map in %.3f seconds" % (time.time() - t0))

    def pacific_trade(self, x, y, x2, y2):
        """Check whether a line goes around the east/west edge of the map"""

        direct_dist = sqrt(abs(x - x2) ** 2 + abs(y - y2) ** 2)
        x_dist_across = self.mapWidth - abs(x - x2)
        dist_across = sqrt(x_dist_across ** 2 + abs(y - y2) ** 2)

        return dist_across < direct_dist

    def save_map(self):
        """Export the current map as a .gif image"""

        self.logger.info("Saving map image...")

        save_name = tk_file_dialog.asksaveasfilename(
            defaultextension=".gif", filetypes=[("GIF file", ".gif")],
            initialdir=os.path.expanduser("~"), title="Save as..")
        if save_name:
            try:
                self.draw_img = self.draw_img.convert("P", palette=Image.ADAPTIVE, dither=Image.NONE, colors=8)
                self.draw_img.save(save_name)
            except Exception as e:
                self.logger.error("Problem saving map image: %s" % e)

    def click_map(self, *args):
        # TODO: implement zoom function
        x = args[0].x
        y = args[0].y
        self.zoomed = not self.zoomed

        self.logger.info("Map clicked at (%i, %i), self.zoomed is now %s" % (x, y, self.zoomed))

    def show_error(self, log_message, user_message):
        if not user_message:
            user_message = log_message
        self.logger.error(log_message)
        tk_message_box.showerror("Error", user_message)


def sign(v):
    if v < 0:
        return -1
    else:
        return 1


def safe_division(x, y):
    return x/y if y else 0


def remove_comments(txt):
    lines = txt.split("\n")
    for i in range(len(lines)):
        lines[i] = lines[i].split("#")[0]
    return "\n".join(lines)


class InvalidTradeNodeException(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.message = msg


class ReadError(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.message = msg


class ParseError(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.message = msg


if __name__ == "__main__":

    debug_level = logging.DEBUG
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            debug_level = eval("logging." + arg)

    tv = TradeViz()
