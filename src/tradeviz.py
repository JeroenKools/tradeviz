"""
Trade Visualizer for EU4
Created on 21 aug. 2013

@author: Jeroen Kools
"""

# TODO: implement zoom function
# TODO: Nodes show options: Player abs trade power, player rel trade power, total trade power
# TODO: Improve handling of arrows intersecting nodes
# TODO: Show countries option: all, players, none
# TODO: Full, tested support for Mac and Linux

# DEPENDENDIES:
# PyParsing: http://pyparsing.wikispaces.com or use 'pip install pyparsing'
# Python Imaging Library: http://www.pythonware.com/products/pil/
# On Ubuntu: aptitude install python-tk python-imaging python-imaging-tk python-pyparsing

# standardlib stuff
import logging
import time
import re
import os
import sys
import json
import zipfile
import psutil
from math import sqrt, ceil, log1p
from packaging import version
import multiprocessing as mp

# GUI stuff
import tkinter as tk
import tkinter.messagebox
import tkinter.filedialog
import tkinter.ttk as ttk
from PIL import Image, ImageTk, ImageDraw

# Tradeviz components
import pyparsing
import NodeGrammar
import TradeGrammar
import util

# globals
provinceBMP = "../res/worldmap.gif"

# Colors
LIGHT_SLATE = "#36434b"
DARK_SLATE = "#29343a"
BTN_BG = "#364555"
BANNER_BG = "#9E9186"
WHITE = "#fff"
BLACK = "#000"

# Fonts
SMALL_FONT = ("Cambria", 12)
BIG_FONT = ("Cambria", 18, "bold")

VERSION = "1.5.0"
COMPATIBILITY_VERSION = version.Version("1.35.3")  # EU4 version
APP_NAME = "EU4 Trade Visualizer"


class UI:
    def __init__(self):
        self.arrowLabels = None
        self.arrow_scale_var = None
        self.canvas = None
        self.done = None
        self.goTime = None
        self.mapDraw = None
        self.map_img = None
        self.mod_path_combo_box = None
        self.mod_path_var = None
        self.nodes_show_var = None
        self.save_entry = None
        self.show_zero_var = None


def get_trade_data(trade_section_text, queue, previous_lines):
    """Extract the trade data from the selected save file"""
    logging.basicConfig(filename="tradeviz_getTradeData.log", filemode="w", level=logging.DEBUG,
                        format="[%(asctime)s] %(levelname)s: %(message)s",
                        datefmt="%Y/%m/%d %H:%M:%S")
    logging.info("Parsing %i chars" % len(trade_section_text))
    t0 = time.time()

    logging.debug("Parsing trade section...")
    result = TradeGrammar.tradeSection.parseString(trade_section_text)
    try:
        trade_section_dict = result.asDict()
        node_data = {}
    except AttributeError as e:
        util.show_error(e, f"Failed to parse save file trade section. {e}")
        return
    except pyparsing.ParseException as e:
        error_message = "Error: " + str(e)
        try:
            line_num = re.search(R"line:(\d+)", str(e))
            line_num = line_num.groups()[0]
            correct_line_num = str(int(line_num) + previous_lines)
            error_message = re.sub(f"line:{line_num}", f"line:{correct_line_num}", error_message)
            print(f"----------------------------\n" +
                  f"{e.line}\n{' ' * (e.column - 1)}^\n{error_message}")
        except AttributeError:
            pass
        util.show_error(e, "Can't read file! " + error_message)
        return

    logging.info("Finished parsing save in %.3f seconds" % (time.time() - t0))
    logging.debug("Processing parsed results")

    max_current = 0
    max_local = 0
    max_incoming = 0

    for nodeDict in trade_section_dict["Nodes"]:
        node_name = list(nodeDict.keys())[0]
        node = {}
        for key in nodeDict[node_name]:
            if key not in ["quotedName", "incomingFromNode", "incomingValue"]:
                node[key] = nodeDict[node_name][key]
            elif key in ["incomingFromNode", "incomingValue"]:
                node[key] = nodeDict[node_name][key]

            if key == "currentValue":
                max_current = max(max_current, nodeDict[node_name][key])
            if key == "localValue":
                max_local = max(max_local, nodeDict[node_name][key])
            if key == "incomingValue":
                max_incoming = max(max_incoming, *nodeDict[node_name][key])

        node_data[nodeDict[node_name]["quotedName"][0]] = node

    try:
        logging.debug("Sevilla:\n\t%s" % node_data["sevilla"])
        logging.debug("max current value: %s" % max_current)
        logging.debug("max incoming value: %s" % max_incoming)
    except KeyError:
        logging.warning("Trade node Sevilla not found! Save file is either from a modded game or malformed!")

    queue.put({"nodeData": node_data,
               "maxCurrent": max_current,
               "maxLocal": max_local,
               "maxIncoming": max_incoming})
    sys.exit()


class TradeViz:
    """Main class for Europa Universalis Trade Visualizer"""

    def __init__(self):
        logging.debug("Initializing application")
        logging.info(f"Using Pyparsing version {pyparsing.__version__}")
        self.root = tk.Tk()
        self.root.withdraw()

        self.paneHeight = 195
        self.w, self.h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.title("%s v%s" % (APP_NAME, VERSION))
        self.root.bind("<Escape>", lambda x: self.exit("Escape key pressed"))
        self.root.wm_protocol("WM_DELETE_WINDOW", lambda: self.exit("Close Window"))
        self.zero_arrows = []
        self.config = {}
        self.ui = UI()
        self.node_data = None
        self.province_locations = None
        self.max_incoming = 0
        self.max_current = 0
        self.max_local = 0

        try:
            self.root.iconbitmap(r"../res/merchant.ico")
        except Exception as e:
            logging.error("Error setting application icon (expected on Unix): %s" % e)

        try:
            self.ui.map_img = Image.open(provinceBMP).convert("RGB")
            self.map_width = self.ui.map_img.size[0]
            self.map_height = self.ui.map_img.size[1]
            self.ui.map_img.thumbnail((self.w - 10, self.h), Image.BICUBIC)
            self.ui.draw_img = self.ui.map_img.convert("RGB")
            self.map_thumb_size = self.ui.map_img.size
            self.ratio = self.map_thumb_size[0] / float(self.map_width)
            self.province_image = ImageTk.PhotoImage(self.ui.map_img)
        except Exception as e:
            logging.critical("Error preparing the world map!\n%s" % e)

        logging.debug("Setting up GUI")
        self.setup_gui()
        self.trade_nodes = []
        self.player = ""
        self.date = ""
        self.zoomed = False
        self.save_version = ""
        self.pre_trade_section_lines = 0
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(7, weight=1)
        self.get_config()
        self.root.deiconify()

        # self.root.focus_set()
        logging.debug("Entering main loop")
        self.root.mainloop()

    def get_config(self):
        """Retrieve settings from config file"""

        logging.debug("Getting config")

        if os.path.exists(r"../tradeviz.cfg"):
            with open(r"../tradeviz.cfg") as f:
                self.config = json.load(f)

        if "savefile" in self.config:
            self.ui.save_entry.insert(0, self.config["savefile"])
        if "showZeroRoutes" in self.config:
            self.ui.show_zero_var.set(self.config["showZeroRoutes"])
        if "nodesShow" in self.config:
            self.ui.nodes_show_var.set(self.config["nodesShow"])
        if "lastModPath" in self.config:
            self.ui.mod_path_var.set(self.config["lastModPath"])
        if "modPaths" in self.config:
            self.ui.mod_path_combo_box.configure(values=[""] + self.config["modPaths"])
        if "arrowScale" in self.config:
            self.ui.arrow_scale_var.set(self.config["arrowScale"])

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

        logging.debug("Saving config")

        with open(r"../tradeviz.cfg", "w") as f:
            json.dump(self.config, f)

    def get_install_dir(self):
        """Find the EU4 install path and store it in the config for later use"""

        logging.debug("Getting install dir")
        self.config["installDir"] = util.search_install_dir()

        if "installDir" not in self.config:
            self.config["installDir"] = ""

        if self.config["installDir"] == "" or not os.path.exists(self.config["installDir"]):
            util.show_error("EU4 installation folder not found!",
                            "Europa Universalis 4 installation could not be found! " +
                            "The program needs to read some files from the game to work correctly. " +
                            "Please select your installation folder manually.")
            folder = tk.filedialog.askdirectory(initialdir="/")
            if os.path.exists(os.path.join(folder, "common")):
                self.config["installDir"] = folder

    def setup_gui(self):
        """Initialize the user interface elements"""

        self.ui.canvas = tk.Canvas(self.root, width=self.map_thumb_size[0], height=self.map_thumb_size[1],
                                   highlightthickness=0, border=5, relief="flat", bg=DARK_SLATE)
        self.ui.canvas.grid(row=1, column=0, columnspan=4, sticky="W", padx=5)
        self.ui.canvas.bind("<Button-1>", self.click_map)
        self.setup_tk_styles()
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
        self.ui.save_entry = tk.Entry(self.root, bd=0, border=0, font=SMALL_FONT, bg=LIGHT_SLATE, fg="white")
        self.ui.save_entry.config(highlightbackground="red", border=3, relief="flat")
        self.ui.save_entry.grid(row=2, column=1, columnspan=2, sticky="WE", padx=6, pady=4, ipady=0)

        tk.Label(self.root, text="Mod:", bg=DARK_SLATE, fg=WHITE,
                 font=SMALL_FONT).grid(row=3, column=0, padx=(6, 2), pady=2, sticky="W")
        self.ui.mod_path_var = tk.StringVar()
        self.ui.mod_path_combo_box = ttk.Combobox(self.root, textvariable=self.ui.mod_path_var, values=[""],
                                                  state="readonly",
                                                  font=SMALL_FONT, style="My.TCombobox")
        self.ui.mod_path_combo_box.grid(row=3, column=1, columnspan=2, sticky="WE", padx=6, pady=2)
        self.ui.mod_path_var.trace("w", self.mod_path_changed)

        tk.Label(self.root, text="Nodes show:", bg=DARK_SLATE, fg=WHITE, font=SMALL_FONT).grid(row=4, column=0,
                                                                                               padx=(6, 2), pady=2,
                                                                                               sticky="W")
        self.ui.nodes_show_var = tk.StringVar()
        self.ui.nodes_show_var.set("Total value")
        self.ui.nodes_show = ttk.Combobox(self.root, textvariable=self.ui.nodes_show_var,
                                          values=["Local value", "Total value"],
                                          state="readonly", font=SMALL_FONT, style="My.TCombobox")
        self.ui.nodes_show["background"] = WHITE
        self.ui.nodes_show["foreground"] = DARK_SLATE
        self.ui.nodes_show.grid(row=4, column=1, columnspan=2, sticky="W", padx=6, pady=2)
        self.ui.nodes_show_var.trace("w", self.nodes_show_changed)

        tk.Label(self.root, text="Arrow scaling:", bg=DARK_SLATE, fg=WHITE, font=SMALL_FONT).grid(row=5, column=0,
                                                                                                  padx=(6, 2), pady=2,
                                                                                                  sticky="W")
        self.ui.arrow_scale_var = tk.StringVar()
        self.ui.arrow_scale_var.set("Square root")
        self.ui.arrow_scale = ttk.Combobox(self.root, textvariable=self.ui.arrow_scale_var,
                                           values=["Linear", "Square root", "Logarithmic"],
                                           state="readonly", font=SMALL_FONT, style="My.TCombobox")
        self.ui.arrow_scale["background"] = WHITE
        self.ui.arrow_scale["foreground"] = DARK_SLATE

        self.ui.arrow_scale.grid(row=5, column=1, columnspan=2, sticky="W", padx=6, pady=2)
        self.ui.arrow_scale_var.trace("w", self.arrow_scale_changed)

        self.ui.show_zero_var = tk.IntVar(value=1)
        self.ui.show_zeroes = tk.Checkbutton(self.root, text="Show unused trade routes",
                                             bg=DARK_SLATE, fg=WHITE, font=SMALL_FONT, selectcolor=LIGHT_SLATE,
                                             activebackground=DARK_SLATE, activeforeground=WHITE,
                                             variable=self.ui.show_zero_var, command=self.toggle_show_zeroes)
        self.ui.show_zeroes.grid(row=6, column=0, columnspan=2, sticky="W", padx=6, pady=2)

        # Buttons

        self.ui.browse_file_btn = tk.Button(self.root, text="Browse...", command=self.browse_save,
                                            bg=BTN_BG, fg=WHITE, font=SMALL_FONT, relief="ridge")
        self.ui.browse_file_btn.grid(row=2, column=3, sticky="WSEN", padx=7, pady=3)

        self.ui.browse_mod_folder_btn = tk.Button(self.root, text="Browse...", command=self.browse_mod,
                                                  bg=BTN_BG, fg=WHITE, font=SMALL_FONT, relief="ridge")
        self.ui.browse_mod_folder_btn.grid(row=3, column=3, sticky="WSEN", padx=7, pady=3, ipady=1)

        self.ui.go_button = tk.Button(self.root, text="Go!", command=self.go, bg=BTN_BG, fg=WHITE,
                                      font=SMALL_FONT + ("bold",), relief="ridge")
        self.ui.go_button.grid(row=7, column=1, sticky="SE", ipadx=20, padx=7, pady=15)

        self.ui.save_img_button = tk.Button(self.root, text="Save Map", command=self.save_map, bg=BTN_BG, fg=WHITE,
                                            font=SMALL_FONT, relief="ridge")
        self.ui.save_img_button.grid(row=7, column=2, sticky="SE", padx=7, pady=15)

        self.ui.exit_button = tk.Button(self.root, text="Exit", command=lambda: self.exit("Button"),
                                        bg=BTN_BG, fg=WHITE, font=SMALL_FONT, relief="ridge")
        self.ui.exit_button.grid(row=7, column=3, sticky="SWE", padx=7, pady=15)

    def setup_tk_styles(self):
        style = ttk.Style()
        style.theme_create(
            'tradeviz_style',
            parent='alt',
            settings={'TCombobox': {
                'configure':
                    {'selectforeground': DARK_SLATE,
                     'selectbackground': WHITE,
                     'fieldforeground': DARK_SLATE,
                     'fieldbackground': WHITE,
                     'foreground': DARK_SLATE,
                     'background': WHITE,
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
        self.root.option_add("*TCombobox*Listbox*Background", WHITE)
        self.root.option_add("*TCombobox*Listbox*Foreground", DARK_SLATE)
        style.theme_use('tradeviz_style')

    def browse_save(self, _event=None):
        """Let the user browseSave for an EU4 save file to be used by the program"""

        logging.debug("Browsing for save file")

        initial_dir = "."
        if "savefile" in self.config:
            initial_dir = os.path.dirname(self.config["savefile"])

        filename = tkinter.filedialog.askopenfilename(filetypes=[("EU4 Saves", "*.eu4")], initialdir=initial_dir)
        logging.info("Selected save file %s" % os.path.basename(filename))
        self.config["savefile"] = filename
        self.save_config()

        self.ui.save_entry.delete(0, tk.END)
        self.ui.save_entry.insert(0, self.config["savefile"])

    def browse_mod(self, _event=None):

        logging.debug("Browsing for mod")

        init_dir = "/"
        if self.config["lastModPath"]:
            init_dir = os.path.split(self.config["lastModPath"])[0]
        else:
            for path in self.config["modPaths"]:
                if path:  # not empty
                    init_dir = os.path.basename(path)
                    break

        mod_path = tk.filedialog.askopenfilename(filetypes=[("EU4 Mods", "*.mod")], initialdir=init_dir)

        logging.debug("Selected mod path %s" % mod_path)

        mod_zip = mod_path.replace(".mod", ".zip")
        mod_dir = mod_path.replace(".mod", "")

        if not os.path.exists(mod_zip) and not os.path.exists(mod_dir):
            if mod_path:
                util.show_error("ModDir %s and modzip %s do not appeat to be a valid mod" % (mod_dir, mod_zip),
                                "This does not seem to be a valid mod path!")
            return

        self.ui.mod_path_var.set(mod_path)
        if mod_path not in self.config["modPaths"]:
            self.config["modPaths"] += [mod_path]

        self.config["lastModPath"] = mod_path

    def go(self, _event=None):
        """Start parsing the selected save file and show the results on the map"""

        logging.info("Processing save file")
        self.ui.done = False
        self.ui.goTime = time.time()
        self.clear_map()

        if self.config["savefile"]:
            try:
                txt = self.get_save_text()
            except ReadError as e:
                util.show_error("Failed to get savefile text: " + e.message,
                                "This save file %s and can't be processed by %s" % (e.message, APP_NAME))
                self.draw_map(True)
                return

            error_message = f"{APP_NAME} could not parse this file. You might be trying to open a corrupted save, " + \
                            "or a save created with an unsupported mod or game version. "
            try:
                trade_section = txt[1]  # drop part before trade section starts
                trade_section = trade_section.split("production_leader")[0]  # drop the part after the end

                # Remove irrelevant, empty country power sections to speed up parsing
                trade_section = re.sub(R"\w{3}={\s+max_demand=[\d.]+\s+}", "", trade_section)

                # Use multiprocessing to parse the save file without blocking the UI thread
                output_queue = mp.SimpleQueue()
                trade_process = mp.Process(target=get_trade_data,
                                           args=(trade_section, output_queue, self.pre_trade_section_lines))
                psutil_process = psutil.Process(trade_process.pid)
                if sys.platform == "win32":
                    psutil_process.nice(psutil.IDLE_PRIORITY_CLASS)
                    psutil_process.ionice(psutil.IOPRIO_LOW)
                else:
                    psutil_process.nice(10)
                    psutil_process.ionice(psutil.IOPRIO_CLASS_IDLE)

                trade_process.start()
                wait_icon_angle = 0
                i = 0

                logging.debug("Entering while loop")
                while trade_process.is_alive():
                    self.do_wait_icon(wait_icon_angle)
                    wait_icon_angle -= 12
                    i += 1
                    time.sleep(0.05)

                trade_data = output_queue.get()
                trade_process.join()
                trade_process.close()
                logging.debug("Parsing process complete")
                self.on_parse_complete(trade_data)
            except IndexError as e:
                util.show_error(e, "Can't read file! " + error_message)
            except Exception as e:
                error_message = "Unexpected error: " + error_message
                print(type(e), e, e.__context__)
                util.show_error(e, "Can't read file! " + error_message)
                raise e

            try:
                self.draw_map(True)
            except InvalidTradeNodeException as e:
                util.show_error("Invalid trade node index: %s" % e,
                                "Save file contains invalid trade node info. " +
                                "If your save is from a modded game, please indicate the mod folder and try again.")

    def on_parse_complete(self, trade_data):
        self.node_data = trade_data["nodeData"]
        self.max_local = trade_data["maxLocal"]
        self.max_current = trade_data["maxCurrent"]
        self.max_incoming = trade_data["maxIncoming"]
        self.get_node_data()

    def do_wait_icon(self, angle=0):

        my = self.h / 2 - self.paneHeight + 40
        mx = self.w / 2
        radius = 16
        arcs = [self.ui.canvas.create_arc(mx - radius, my - radius, mx + radius, my + radius,
                                          fill=WHITE, outline=WHITE, start=angle),
                self.ui.canvas.create_arc(mx - radius, my - radius, mx + radius, my + radius,
                                          fill=WHITE, outline=WHITE, start=(angle + 180))]

        self.ui.canvas.itemconfig(arcs[0], start=angle)
        self.ui.canvas.itemconfig(arcs[1], start=angle + 180)
        self.ui.canvas.update_idletasks()

        for arc in arcs:
            self.ui.canvas.delete(arc)

    def get_save_text(self):
        """Extract the text from the selected save file"""

        self.ui.canvas.create_text((self.map_thumb_size[0] / 2, self.map_thumb_size[1] / 2),
                                   text="Please wait... Save file is being processed...",
                                   fill="white",
                                   font=SMALL_FONT)
        self.root.update()
        logging.debug("Reading save file %s" % os.path.basename(self.config["savefile"]))

        with open(self.config["savefile"], encoding="latin-1", mode="r") as f:
            try:
                txt = f.read()
            except UnicodeDecodeError:
                return

            txt = self.check_for_compression(txt)
            self.check_for_ironman(txt)
            self.check_for_version(txt)

            if not txt.startswith("EU4txt"):
                logging.error("Savefile starts with %s, not EU4txt" % txt[:10])
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
            self.pre_trade_section_lines = txt[0].count("\n")

        return txt

    @staticmethod
    def check_for_ironman(txt):
        if txt.startswith("EU4bin"):
            raise ReadError("appears to be an Ironman save")

    def check_for_compression(self, txt):
        """Check whether the save file text is compressed. If so, return uncompressed text, otherwise return the text
        unchanged """
        if txt[:2] == "PK":
            logging.info("Save file is compressed, unzipping...")
            zipped_save = zipfile.ZipFile(self.config["savefile"])
            filename = [x for x in zipped_save.namelist() if x.endswith(".eu4") or x == "gamestate"][0]
            unzipped_save = zipped_save.open(filename)
            txt = unzipped_save.read().decode("latin-1")
            return txt
        else:
            return txt

    def check_for_version(self, txt):
        version_tuple = re.findall(R"first=(\d+)\s+second=(\d+)\s+third=(\d+)", txt[:500])
        if not version_tuple:
            logging.warning("Could not find version info!")
        else:
            version_tuple = version_tuple[0]
            self.save_version = version.Version("%s.%s.%s" % version_tuple)
            logging.info("Savegame version is %s" % self.save_version)
            if self.save_version > COMPATIBILITY_VERSION:
                tkinter.messagebox.showwarning("Version warning",
                                               ("This savegame is from an a newer EU4 version (%s) than " +
                                                "the version this tool designed to work for (%s). " +
                                                "It might not work correctly!") % (
                                                   self.save_version.__str__(), COMPATIBILITY_VERSION.__str__()))

    def toggle_show_zeroes(self, _event=None):
        """Turn the display of trade routes with a value of zero on or off"""

        logging.debug("Show zeroes toggled")
        self.config["showZeroRoutes"] = self.ui.show_zero_var.get()
        self.root.update()

        if not self.zero_arrows and self.ui.show_zero_var.get():
            self.draw_map()
        else:
            for itemId in self.zero_arrows:
                if self.ui.show_zero_var.get():
                    self.ui.canvas.itemconfig(itemId, state="normal")
                else:
                    self.ui.canvas.itemconfig(itemId, state="hidden")

        self.save_config()

    def nodes_show_changed(self, *_args):
        self.config["nodesShow"] = self.ui.nodes_show_var.get()
        self.draw_map()

    def arrow_scale_changed(self, *_args):
        self.config["arrowScale"] = self.ui.arrow_scale_var.get()
        self.draw_map()

    def mod_path_changed(self, *_args):
        self.config["lastModPath"] = self.ui.mod_path_var.get()

    def exit(self, reason=""):
        """Close the program"""

        self.save_config()
        self.root.update()
        logging.info("Exiting... (%s)" % reason)
        logging.shutdown()
        self.root.quit()

    def get_node_name(self, node_id):
        node = self.trade_nodes[node_id - 1]
        return node[0]

    def get_node_location(self, node_id):
        if node_id > len(self.trade_nodes) + 1:
            raise InvalidTradeNodeException(node_id)
        node = self.trade_nodes[node_id - 1]
        province_id = node[1]

        for loc in self.province_locations:
            if loc[0] == province_id:
                return loc[1:]

    def get_node_data(self):
        """Retrieve trade node and province information from the game or mod files"""

        logging.debug("Getting node data")

        trade_nodes = r"common/tradenodes/00_tradenodes.txt"
        positions = r"map/positions.txt"

        mod_path = self.ui.mod_path_combo_box.get()
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
                if os.path.normpath(trade_nodes) in z.namelist():
                    logging.debug("Using tradenodes file from zipped mod")
                    with z.open(trade_nodes) as f:
                        txt = f.read()
                else:
                    trade_nodes_file = os.path.join(self.config["installDir"], trade_nodes)
                    logging.debug("Using default tradenodes file")

                    with open(trade_nodes_file, "r") as f:
                        txt = f.read()

            else:
                if mod_type == "dir" and os.path.exists(os.path.join(mod_dir, trade_nodes)):
                    trade_nodes_file = os.path.join(mod_dir, trade_nodes)
                    logging.debug("Using tradenodes file from mod directory")
                else:
                    trade_nodes_file = os.path.join(self.config["installDir"], trade_nodes)
                    logging.debug("Using default tradenodes file")

                with open(trade_nodes_file, "r") as f:
                    txt = f.read()
        except IOError as e:
            logging.critical("Could not find trade nodes file: %s" % e)

        txt = util.remove_comments(txt)
        trade_nodes = NodeGrammar.nodes.parseString(txt)
        logging.info("%i tradenodes found in %i chars" % (len(trade_nodes), len(txt)))

        for i, tradeNode in enumerate(trade_nodes):
            trade_nodes[i] = (tradeNode["name"], tradeNode["location"])

        self.trade_nodes = trade_nodes

        # Now get province positions
        try:
            if mod_type == "zip":
                z = zipfile.ZipFile(mod_zip)
                if os.path.normpath(positions) in z.namelist():
                    logging.debug("Using positions file from zipped mod")
                    with z.open(positions) as f:
                        txt = f.read()
                else:
                    trade_nodes_file = os.path.join(self.config["installDir"], positions)
                    logging.debug("Using default tradenodes file")

                    with open(trade_nodes_file, "r") as f:
                        txt = f.read()
            else:
                if mod_type == "dir" and os.path.exists(os.path.join(mod_dir, positions)):
                    positions_file = os.path.join(mod_dir, positions)
                    logging.debug("Using positions file from mod directory")
                else:
                    positions_file = os.path.join(self.config["installDir"], positions)
                    logging.debug("Using default positions file")

                with open(positions_file, encoding="latin-1", mode="r") as f:
                    txt = f.read()
        except IOError as e:
            logging.critical("Could not find locations file: %s" % e)

        locations = re.findall(r"(\d+)=\s*{\s*position=\s*{\s*([\d.]*)\s*([\d.]*)", txt)
        for i in range(len(locations)):
            a, b, c = locations[i]

            locations[i] = (int(a), float(b), self.map_height - float(c))  # invert y coordinate :)

        self.province_locations = locations
        logging.info("Found %i province locations" % len(self.province_locations))

    def get_node_radius(self, node):
        """Calculate the radius for a trade node given its value"""

        if self.config["nodesShow"] == "Total value":
            if "currentValue" in node:
                value = node["currentValue"] / self.max_current
            else:
                value = 0
        elif self.config["nodesShow"] == "Local value":
            if "localValue" in node:
                value = node["localValue"] / self.max_local
            else:
                value = 0
        else:
            logging.error("Invalid nodesShow option: %s" % self.config["nodesShow"])
            value = 0

        return 5 + int(7 * value)

    def get_line_width(self, value) -> float:

        arrow_scale_style = self.ui.arrow_scale_var.get()

        if value <= 0:
            return 1

        elif arrow_scale_style == "Linear":
            return int(ceil(10 * value / self.max_incoming))

        elif arrow_scale_style == "Square root":
            return int(round(10 * sqrt(value) / sqrt(self.max_incoming)))

        elif arrow_scale_style == "Logarithmic":
            return int(round(10 * log1p(value) / log1p(self.max_incoming)))

    def intersects_node(self, node1, node2):
        """
        Check whether a trade route intersects a trade node circle (other than source and target nodes)
        See http://mathworld.wolfram.com/Circle-LineIntersection.html
        """

        # TODO: clearer variable names in this section
        for n, node3 in enumerate(self.trade_nodes):
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
                # Infinite line intersects, check whether the center node is inside the rectangle
                # defined by the other nodes.
                if min(x1, x2) < 0 < max(x1, x2) and min(y1, y2) < 0 < max(y1, y2):
                    logging.debug("%s is intersected by a trade route between %s and %s" %
                                  (self.get_node_name(n + 1), self.get_node_name(node1), self.get_node_name(node2)))
                    return True

    def draw_arrow(self, from_node, to_node, value, to_radius):
        """Draw an arrow between two nodes on the map"""

        if value <= 0 and not self.ui.show_zero_var.get():
            return

        x2, y2 = self.get_node_location(from_node)
        x, y = self.get_node_location(to_node)
        is_pacific = self.pacific_trade(x, y, x2, y2)

        # adjust for target node radius
        dx = x - x2
        if is_pacific:
            if x > x2:
                dx = x2 - self.map_width - x
            else:
                dx = self.map_width - x + x2
        dy = y - y2
        radius_ratio = max(1.0, sqrt(dx ** 2 + dy ** 2))
        radius_fraction = to_radius / radius_ratio

        # adjust to stop at node circle's edge
        x -= 3 * dx * radius_fraction
        y -= 3 * dy * radius_fraction

        # rescale to unit length
        dx /= radius_ratio
        dy /= radius_ratio

        ratio = self.ratio
        line_width = self.get_line_width(value)
        arrow_shape = (max(8.0, line_width * 2), max(10.0, line_width * 2.5), max(5.0, line_width))
        w = max(5 / ratio, 1.5 * line_width / ratio)
        line_color = "#000" if value > 0 else "#ff0"

        if not is_pacific:
            center_of_line = ((x + x2) / 2 * ratio, (y + y2) / 2 * ratio)

            if self.intersects_node(from_node, to_node):
                d = 20
                center_of_line = (center_of_line[0] + d, center_of_line[1] + d)
                z1 = self.ui.canvas.create_line((x * ratio, y * ratio, center_of_line[0], center_of_line[1]),
                                                width=line_width, arrow=tk.FIRST, arrowshape=arrow_shape,
                                                fill=line_color)
                z2 = self.ui.canvas.create_line((center_of_line[0], center_of_line[1], x2 * ratio, y2 * ratio),
                                                width=line_width, fill=line_color)

                z3 = self.ui.mapDraw.line((x * ratio, y * ratio, center_of_line[0], center_of_line[1]),
                                          width=line_width, fill=line_color)
                z4 = self.ui.mapDraw.polygon(
                    (x * ratio, y * ratio,
                     (x - w * dx + w * dy) * ratio, (y - w * dx - w * dy) * ratio,
                     (x - w * dx - w * dy) * ratio, (y + w * dx - w * dy) * ratio
                     ),
                    outline=line_color, fill=line_color)

                z5 = self.ui.mapDraw.line((center_of_line[0], center_of_line[1], x2 * ratio, y2 * ratio),
                                          width=line_width, fill=line_color)

                if value == 0:
                    self.zero_arrows += [z1, z2, z3, z4, z5]

            else:  # not intersects_node(from_node, to_node)
                z1 = self.ui.canvas.create_line((x * ratio, y * ratio, x2 * ratio, y2 * ratio),
                                                width=line_width, arrow=tk.FIRST, arrowshape=arrow_shape,
                                                fill=line_color)

                z2 = self.ui.mapDraw.line((x * ratio, y * ratio, x2 * ratio, y2 * ratio),
                                          width=line_width, fill=line_color)

                z3 = self.ui.mapDraw.polygon(
                    (x * ratio, y * ratio,
                     (x - w * dx + w * dy) * ratio, (y - w * dx - w * dy) * ratio,
                     (x - w * dx - w * dy) * ratio, (y + w * dx - w * dy) * ratio
                     ),
                    outline=line_color, fill=line_color)

                if value == 0:
                    self.zero_arrows += [z1, z2, z3]

            self.ui.arrowLabels.append([center_of_line, value])

        else:  # Trade route crosses edge of map

            if x < x2:  # Asia to America
                z0 = self.ui.canvas.create_line((x * ratio, y * ratio, (-self.map_width + x2) * ratio, y2 * ratio),
                                                width=1, fill=line_color, arrow=tk.FIRST, arrowshape=arrow_shape)
                z1 = self.ui.canvas.create_line(((self.map_width + x) * ratio, y * ratio, x2 * ratio, y2 * ratio),
                                                width=1, fill=line_color, arrow=tk.FIRST, arrowshape=arrow_shape)

                z2 = self.ui.mapDraw.line((x * ratio, y * ratio, (-self.map_width + x2) * ratio, y2 * ratio),
                                          width=1, fill=line_color)
                z3 = self.ui.mapDraw.line(((self.map_width + x) * ratio, y * ratio, x2 * ratio, y2 * ratio),
                                          width=1, fill=line_color)
                z4 = self.ui.mapDraw.polygon(
                    (x * ratio, y * ratio,
                     (x - w * dx + w * dy) * ratio, (y - w * dx - w * dy) * ratio,
                     (x - w * dx - w * dy) * ratio, (y + w * dx - w * dy) * ratio
                     ),
                    outline=line_color, fill=line_color)

                # fraction of trade route left of "date line"
                f = abs(self.map_width - float(x2)) / (self.map_width - abs(x - x2))
                # y coordinate where trade route crosses date line
                yf = y2 + f * (y - y2)

                center_of_line = (x / 2 * ratio, (yf + y) / 2 * ratio)
                if value == 0:
                    self.zero_arrows += [z0, z1, z2, z3, z4]

            else:  # Americas to Asia
                z0 = self.ui.canvas.create_line((x * ratio, y * ratio, (self.map_width + x2) * ratio, y2 * ratio),
                                                width=1, fill=line_color, arrow=tk.FIRST, arrowshape=arrow_shape)
                z1 = self.ui.canvas.create_line(((-self.map_width + x) * ratio, y * ratio, x2 * ratio, y2 * ratio),
                                                width=1, fill=line_color, arrow=tk.FIRST, arrowshape=arrow_shape)

                z2 = self.ui.mapDraw.line((x * ratio, y * ratio, (self.map_width + x2) * ratio, y2 * ratio),
                                          width=1, fill=line_color)
                z3 = self.ui.mapDraw.line(((-self.map_width + x) * ratio, y * ratio, x2 * ratio, y2 * ratio),
                                          width=1, fill=line_color)
                z4 = self.ui.mapDraw.polygon(
                    (x * ratio, y * ratio,
                     (x - w * dx + w * dy) * ratio, (y - w * dx - w * dy) * ratio,
                     (x - w * dx - w * dy) * ratio, (y + w * dx - w * dy) * ratio
                     ),
                    outline=line_color, fill=line_color)

                f = abs(self.map_width - float(x)) / (self.map_width - abs(x - x2))
                yf = y + f * (y2 - y)

                center_of_line = ((self.map_width + x) / 2 * ratio, (yf + y) / 2 * ratio)

            self.ui.arrowLabels.append([center_of_line, value])

            if value == 0:
                self.zero_arrows += [z0, z1, z2, z3, z4]

    def clear_map(self, update=False):
        self.ui.canvas.create_image((0, 0), image=self.province_image, anchor=tk.NW)
        self.ui.drawImg = self.ui.map_img.convert("RGB")
        self.ui.mapDraw = ImageDraw.Draw(self.ui.drawImg)
        if update:
            self.ui.canvas.update()

    def draw_map(self, clear=False):
        """Top level method for redrawing the world map and trade network"""

        logging.debug("Drawing map..")
        t0 = time.time()

        self.clear_map(clear)
        self.ui.done = True
        ratio = self.ratio
        self.zero_arrows = []

        # draw incoming trade arrows
        t1 = time.time()
        n_arrows = 0
        self.ui.arrowLabels = []

        for n, node in enumerate(self.trade_nodes):
            _x, _y = self.get_node_location(n + 1)

            try:
                data = self.node_data[node[0]]

                if "incomingValue" in data:
                    for i, value in enumerate(data["incomingValue"]):
                        from_node_nr = data["incomingFromNode"][i]
                        if from_node_nr >= len(self.trade_nodes):
                            continue
                        self.draw_arrow(from_node_nr, n + 1, value, self.get_node_radius(data))
                        n_arrows += 1
            except KeyError as e:
                util.show_error("Encountered unknown trade node %s!" % node[0],
                                "An invalid trade node was encountered. Save file doesn't match" +
                                " currently installed EU4 version, or incorrect mod selected.")
                print(self.node_data)
                raise e

        logging.debug("Drew %i arrows in %.2fs" % (n_arrows, time.time() - t1))

        # draw trade arrow labels
        for [centerOfLine, value] in self.ui.arrowLabels:
            if value > 0 or self.ui.show_zero_var.get():
                value_str = "%i" % ceil(value) if (value >= 2 or value <= 0) else ("%.1f" % value)
                z5 = self.ui.canvas.create_text(centerOfLine, text=value_str, fill=WHITE)
                z6 = self.ui.mapDraw.text((centerOfLine[0] - 4, centerOfLine[1] - 4), value_str, fill=WHITE)

                if value == 0:
                    self.zero_arrows += [z5, z6]

        # draw trade nodes and their current value
        n_nodes = 0
        for n, node in enumerate(self.trade_nodes):
            x, y = self.get_node_location(n + 1)

            data = self.node_data[node[0]]
            s = self.get_node_radius(data)
            trade_node_color = BLACK
            v = 0

            if self.config["nodesShow"] == "Total value":
                if "currentValue" in data:
                    v = data["currentValue"]
                else:
                    v = 0
                trade_node_color = "#d00"
            elif self.config["nodesShow"] == "Local value":
                if "localValue" in data:
                    v = data["localValue"]
                else:
                    v = 0
                trade_node_color = "#90c"

            digits = len("%i" % v)

            self.ui.canvas.create_oval((x * ratio - s, y * ratio - s, x * ratio + s, y * ratio + s),
                                       outline=trade_node_color, fill=trade_node_color)
            self.ui.canvas.create_text((x * ratio, y * ratio), text=int(v), fill="white")

            self.ui.mapDraw.ellipse((x * ratio - s, y * ratio - s, x * ratio + s, y * ratio + s),
                                    outline=trade_node_color, fill=trade_node_color)
            self.ui.mapDraw.text((x * ratio - 3 * digits, y * ratio - 4), "%d" % v, fill=WHITE)
            n_nodes += 1
        logging.debug("Drew %i nodes" % n_nodes)

        self.ui.canvas.create_text((10, self.map_height * ratio - 60), anchor="nw",
                                   text="Player: %s" % self.player, fill="white")

        self.ui.canvas.create_text((10, self.map_height * ratio - 40), anchor="nw",
                                   text="Date: %s" % self.date, fill="white")

        self.ui.canvas.create_text((10, self.map_height * ratio - 20), anchor="nw",
                                   text="Version: %s" % self.save_version, fill="white")

        self.ui.mapDraw.text((10, self.map_height * ratio - 44), "Player: %s" % self.player, fill=WHITE)
        self.ui.mapDraw.text((10, self.map_height * ratio - 24), "Date: %s" % self.date, fill=WHITE)

        logging.info("Finished drawing map in %.3f seconds" % (time.time() - t0))

    def pacific_trade(self, x, y, x2, y2):
        """Check whether a line goes around the east/west edge of the map"""

        direct_dist = sqrt(abs(x - x2) ** 2 + abs(y - y2) ** 2)
        x_dist_across = self.map_width - abs(x - x2)
        dist_across = sqrt(x_dist_across ** 2 + abs(y - y2) ** 2)

        return dist_across < direct_dist

    def save_map(self):
        """Export the current map as a .gif image"""

        logging.info("Saving map image...")

        save_name = tk.filedialog.asksaveasfilename(defaultextension=".gif", filetypes=[("GIF file", ".gif")],
                                                    initialdir=os.path.expanduser("~"),
                                                    title="Save as..")
        if save_name:
            try:
                self.ui.drawImg = self.ui.drawImg.convert("P", palette=Image.ADAPTIVE, dither=Image.NONE, colors=8)
                self.ui.drawImg.save(save_name)
            except Exception as e:
                logging.error("Problem saving map image: %s" % e)

    def click_map(self, *args):
        x = args[0].x
        y = args[0].y
        self.zoomed = not self.zoomed

        logging.info("Map clicked at (%i, %i), self.zoomed is now %s" % (x, y, self.zoomed))


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

    debuglevel = logging.DEBUG
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            debuglevel = eval("logging." + arg)

    logging.basicConfig(filename="tradeviz.log", filemode="w", level=debuglevel,
                        format="[%(asctime)s] %(levelname)s: %(message)s",
                        datefmt="%Y/%m/%d %H:%M:%S")

    tv = TradeViz()
