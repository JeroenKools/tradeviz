'''
Trade Visualizer for EU4

Created on 21 aug. 2013

@author: Jeroen Kools
'''

VERSION = "1.0.3"

# TODO: 'Nodes show' option: current value, local value, total trade power
# TODO: Show countries option: ALL, specific tag
# TODO: better support for lower resolutions? (1280x720)
# TODO: Use stdlib logging module in order to help solving bug reports
# TODO: support for mods that change the map and/or trade network

from TradeGrammar import tradeSection

# GUI stuff
import Tkinter as tk
import tkFileDialog
import tkMessageBox
from PIL import Image, ImageTk

# standardlib stuff
import time
import re
import os
import sys
import json
from math import sqrt

# globals
provinceBMP = r'../res/worldmap.gif'
WinRegKey = "SOFTWARE\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Steam App 236850"
MacDefaultPath = os.path.expanduser("~/Library/Application Support/Steam/Steamapps/common/Europa Universalis IV")
LinuxDefaultPath = os.path.expanduser("~/Steam/Steamapps/common/Europa Universalis IV")

class TradeViz:
    """Main class for Europa Universalis Trade Visualizer"""
    def __init__(self):
        self.root = tk.Tk()
        self.paneHeight = 100
        self.w, self.h = self.root.winfo_screenwidth() - 15, self.root.winfo_screenheight() - self.paneHeight
        self.root.title("EU4 Trade Visualizer v%s" % VERSION)
        self.root.iconbitmap(r'../res/merchant.ico')

        img = Image.open(provinceBMP)
        self.mapWidth = img.size[0]
        img.thumbnail((self.w, self.h), Image.BICUBIC)
        self.mapThumbSize = img.size
        self.ratio = self.mapThumbSize[0] / float(self.mapWidth)
        self.provinceImage = ImageTk.PhotoImage(img)

        self.setupGUI()

        self.tradenodes = []
        self.drawMap()
        self.root.grid_columnconfigure(1, weight=1)

        self.getConfig()

        self.root.focus_set()
        self.root.mainloop()

    def getConfig(self):
        """Retrieve settings from config file"""

        if os.path.exists(r"../tradeviz.cfg"):
            with open(r'../tradeviz.cfg') as f:
                self.config = json.load(f)
            if "savefile" in self.config:
                self.saveEntry.insert(0, self.config["savefile"])
            if 'showZeroRoutes' in self.config:
                self.showZeroVar.set(self.config["showZeroRoutes"])

        else:
            self.config = {"savefile": "", "showZeroRoutes": 0}

        if not 'installDir' in self.config or not os.path.exists(self.config["installDir"]):
            self.getInstallDir()

        self.tradenodesfile = os.path.join(self.config["installDir"], r"common\tradenodes\00_tradenodes.txt")
        self.locationsfile = os.path.join(self.config["installDir"], r"map\positions.txt")

    def saveConfig(self):
        """Store settings in config file"""

        with open(r'../tradeviz.cfg', 'w') as f:
            json.dump(self.config, f)

    def getInstallDir(self):
        """Find the EU4 install path and store it in the config for later use"""

        if sys.platform == "win32":
            import _winreg
            key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, WinRegKey)
            try:
                i = 0
                while 1:
                    name, val, typ = _winreg.EnumValue(key, i)
                    if name == "InstallLocation":
                        self.config["installDir"] = val
                        break
                    i += 1

            except WindowsError as e:
                print e

        elif sys.platform == "darwin":  # OS X

            if os.path.exists(MacDefaultPath):
                self.config["installDir"] = MacDefaultPath

        else:  # Assume it's Linux
            if os.path.exists(LinuxDefaultPath):
                self.config["installDir"] = LinuxDefaultPath

        if not 'installDir' in self.config or not os.path.exists(self.config["installDir"]):
            if not os.path.exists(self.config["installDir"]):
                msg = "Europa Universalis install location found in Windows registry but location is invalid."

            else:
                msg = "Europa Universalis 4 installation could not be found!"

            tkMessageBox.showerror("Error", msg + " Please select your installation folder manually.")
            folder = tkFileDialog.askdirectory(initialdir="/")
            if os.path.exists(os.path.join(folder, "common")):
                self.config["installDir"] = folder

    def setupGUI(self):
        """Initialize the user interface elements"""

        self.canvas = tk.Canvas(self.root, width=self.mapThumbSize[0], height=self.mapThumbSize[1])
        self.canvas.grid(row=0, column=0, columnspan=3, sticky=tk.W)

        tk.Label(self.root, text="Save file:").grid(row=1, column=0, padx=6, pady=2)
        self.saveEntry = tk.Entry(self.root)
        self.saveEntry.grid(row=1, column=1, sticky=tk.W + tk.E, padx=6, pady=2)

        self.browseFileBtn = tk.Button(self.root, text="Browse...", command=self.browse)
        self.browseFileBtn.grid(row=1, column=2, sticky=tk.E, padx=6, pady=4)

        self.goButton = tk.Button(self.root, text="Go!", command=self.go)
        self.goButton.grid(row=2, column=2, sticky=tk.E + tk.W, padx=6, pady=2)

        self.exitButton = tk.Button(self.root, text="Exit", command=self.exit)
        self.exitButton.grid(row=3, column=2, sticky=tk.E + tk.W, padx=6, pady=2)

        self.showZeroVar = tk.IntVar(value=1)
        self.showZeroes = tk.Checkbutton(self.root, text="Show unused trade routes", variable=self.showZeroVar, command=self.toggleShowZeroes)
        self.showZeroes.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=6, pady=2)

    def browse(self, event=None):
        """Let the user browse for an EU4 save file to be used by the program"""

        initialDir = '.'
        if "savefile" in self.config:
            initialDir = os.path.dirname(self.config["savefile"])

        filename = tkFileDialog.askopenfilename(filetypes=[("EU4 Saves", "*.eu4")], initialdir=initialDir)
        self.config["savefile"] = filename
        self.saveConfig()

        self.saveEntry.delete(0, tk.END)
        self.saveEntry.insert(0, self.config["savefile"])

    def go(self, event=None):
        """Start parsing the selected save file and show the results on the map"""

        if self.config["savefile"]:
            self.getTradeData(self.config["savefile"])
            self.getNodeData()
            self.drawMap()

    def toggleShowZeroes(self, event=None):
        """Turn the display of trade routes with a value of zero on or off"""

        self.config["showZeroRoutes"] = self.showZeroVar.get()
        self.root.update()
        self.drawMap()
        self.saveConfig()


    def exit(self, event=None):
        """Close the program"""

        self.saveConfig()
        self.root.quit()

    def getTradeData(self, savepath):
        """Extract the trade data from the selected save file"""

        self.canvas.create_text((self.mapThumbSize[0] / 2, self.mapThumbSize[1] / 2), text="Please wait... Save file is being processed...", fill="white")
        self.root.update()
        with open(savepath) as f:
            txt = f.read()
            txt = txt.split("trade=")[1]
            txt = txt.split("production_leader=")[0]

        print "Parsing %i chars..." % len(txt)
        t0 = time.time()

        result = tradeSection.parseString(txt)
        d = result.asDict()
        r = {}

        print 'Done in %.3f seconds' % (time.time() - t0)

        self.maxIncoming = 0
        self.maxCurrent = 0

        for n in d['Nodes']:
            d = n.asDict()
            node = {}
            for k in d:
                if k not in ["name" , 'incomingFromNode', 'incomingValue']:
                    node[k] = d[k]
                elif k in ['incomingFromNode', 'incomingValue']:
                    node[k] = d[k].asList()

                if k == "currentValue":
                    self.maxCurrent = max(self.maxCurrent, d[k])
                if k == "incomingValue":
                    self.maxIncoming = max(self.maxIncoming, *d[k].asList())

            r[d["name"][0]] = node

#         print "Seville:\n\t", r["sevilla"]
#         print "----"
#         print "max current value:", self.maxCurrent
#         print "max incoming value:", self.maxIncoming
#         print '----'

        self.nodeData = r

    def getNodeName(self, nodeID):
        node = self.tradenodes[nodeID - 1]
        return node[0]

    def getNodeLocation(self, nodeID):
        node = self.tradenodes[nodeID - 1]
        provinceID = node[1]

        for loc in self.provinceLocations:
            if loc[0] == provinceID:
                return loc[1:]

    def getNodeData(self):
        """Retrieve trade node and province information from the game files"""

        # Get all tradenode provinceIDs
        with open(self.tradenodesfile, 'r') as f:
            txt = f.read()
            tradenodes = re.findall(r"(\w+)=\s*{\s*location=(\d+)", txt)

        for i in range(len(tradenodes)):
            a, b = tradenodes[i]
            tradenodes[i] = (a, int(b))

        self.tradenodes = tradenodes
        assert tradenodes[0] == ('california', 871)

        # Get all province locations
        with open(self.locationsfile, 'r') as f:
            txt = f.read()
            locations = re.findall(r"(\d+)=\s*{\s*position=\s*{\s*([\d\.]*)\s*([\d\.]*)", txt)

        for i in range(len(locations)):
            a, b, c = locations[i]

            locations[i] = (int(a), float(b), 2048 - float(c))

        self.provinceLocations = locations
        assert locations[0] == (1, 3085.0, 325.0)

    def getNodeRadius(self, value):
        """Calculate the radius for a trade node given its value"""

        return 5 + int(7 * value / self.maxCurrent)

    def intersectsNode(self, node1, node2):
        """Check whether a trade route intersects a trade node circle (other than source and target nodes)
        See http://mathworld.wolfram.com/Circle-LineIntersection.html
        """

        for n, node3 in enumerate(self.tradenodes):
            nx, ny = self.getNodeLocation(n + 1)
            data = self.nodeData[node3[0]]
            r = self.getNodeRadius(data['currentValue']) / self.ratio

            # assume circle center is at 0,0
            x2, y2 = self.getNodeLocation(node1)
            x1, y1 = self.getNodeLocation(node2)
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
                # infinite line intersects, check whether the center node is inside the rectangle defined by the other nodes
                if min(x1, x2) < 0 and max(x1, x2) > 0 and min(y1, y2) < 0 and max(y1, y2) > 0:
                    # print "%s is intersected by a trade route between %s and %s" % (self.getNodeName(n + 1), self.getNodeName(node1), self.getNodeName(node2))
                    return True

    def drawArrow(self, fromNode, toNode, value, toRadius):
        """Draw an arrow between two nodes on the map"""

        x2, y2 = self.getNodeLocation(fromNode)
        x, y = self.getNodeLocation(toNode)

        # adjust for target node radius
        dx = x - x2
        if self.pacificTrade(x, y, x2, y2):
            if x > x2:
                dx = x2 - self.mapWidth - x
            else:
                dx = self.mapWidth - x + x2
        dy = y - y2
        l = sqrt(dx ** 2 + dy ** 2)
        radiusFraction = toRadius / l
        x -= radiusFraction * 3 * dx
        y -= radiusFraction * 3 * dy

        ratio = self.ratio
        lineWidth = int(10 * value / self.maxIncoming)
        arrowShape = (max(8, lineWidth * 2), max(10, lineWidth * 2.5), max(5, lineWidth))

        if value > 0:
            linecolor = 'black'
        else:
            if self.showZeroVar.get() == 0:
                return
            linecolor = 'yellow'

        if not self.pacificTrade(x, y, x2, y2):

            centerOfLine = ((x + x2) / 2 * ratio, (y + y2) / 2 * ratio)

            if self.intersectsNode(fromNode, toNode):
                d = 20
                centerOfLine = (centerOfLine[0] + d, centerOfLine[1] + d)
                self.canvas.create_line((x * ratio , y * ratio , centerOfLine[0] , centerOfLine[1]),
                        width=lineWidth, arrow=tk.FIRST, arrowshape=arrowShape, fill=linecolor)
                self.canvas.create_line((centerOfLine[0] , centerOfLine[1], x2 * ratio , y2 * ratio),
                        width=lineWidth, fill=linecolor)

            else:
                self.canvas.create_line((x * ratio , y * ratio , x2 * ratio , y2 * ratio),
                        width=lineWidth, arrow=tk.FIRST, arrowshape=arrowShape, fill=linecolor)

            self.canvas.create_text(centerOfLine, text=int(round(value)), fill='white')

        else:  # Trade route crosses edge of map

            if x < x2:  # Asia to America
                self.canvas.create_line((x * ratio , y * ratio , (-self.mapWidth + x2) * ratio , y2 * ratio),
                                    width=1, fill=linecolor, arrow=tk.FIRST, arrowshape=arrowShape)
                self.canvas.create_line(((self.mapWidth + x) * ratio , y * ratio , x2 * ratio , y2 * ratio),
                                    width=1, fill=linecolor, arrow=tk.FIRST, arrowshape=arrowShape)

                # fraction of trade route left of "date line"
                f = abs(self.mapWidth - float(x2)) / (self.mapWidth - abs(x - x2))
                # y coordinate where trade route crosses date line
                yf = y2 + f * (y - y2)

                centerOfLine = (x / 2 * ratio, (yf + y) / 2 * ratio)

            else:  # Americas to Asia
                self.canvas.create_line((x * ratio , y * ratio , (self.mapWidth + x2) * ratio , y2 * ratio),
                                    width=1, fill=linecolor, arrow=tk.FIRST, arrowshape=arrowShape)
                self.canvas.create_line(((-self.mapWidth + x) * ratio , y * ratio , x2 * ratio , y2 * ratio),
                                    width=1, fill=linecolor, arrow=tk.FIRST, arrowshape=arrowShape)

                f = abs(self.mapWidth - float(x)) / (self.mapWidth - abs(x - x2))
                yf = y + f * (y2 - y)

                centerOfLine = ((self.mapWidth + x) / 2 * ratio, (yf + y) / 2 * ratio)

            self.canvas.create_text(centerOfLine, text=int(value), fill='white')

    def drawMap(self):
        """Top level method for redrawing the world map and trade network"""

        self.root.geometry("%dx%d+0+0" % (self.w, self.mapThumbSize[1] + self.paneHeight))
        self.root.minsize(self.w, self.mapThumbSize[1] + self.paneHeight)
        self.root.maxsize(self.w, self.mapThumbSize[1] + self.paneHeight)
        self.canvas.create_image((0, 0), image=self.provinceImage, anchor=tk.NW)
        ratio = self.ratio

        # draw incoming trade arrows
        for n, node in enumerate(self.tradenodes):
            x, y = self.getNodeLocation(n + 1)

            data = self.nodeData[node[0]]

            if 'incomingValue' in data:
                for i in range(len(data['incomingValue'])):
                    fromNodeNr = data['incomingFromNode'][i]

                    value = data['incomingValue'][i]
                    self.drawArrow(fromNodeNr, n + 1, value, self.getNodeRadius(data['currentValue']))

        # draw trade nodes and their current value
        for n, node in enumerate(self.tradenodes):
            x, y = self.getNodeLocation(n + 1)

            data = self.nodeData[node[0]]
            s = self.getNodeRadius(data['currentValue'])

            self.canvas.create_oval((x * ratio - s, y * ratio - s, x * ratio + s, y * ratio + s), outline="red",
                                    fill="red")
            self.canvas.create_text((x * ratio, y * ratio), text=int(data['currentValue']), fill='white')

    def pacificTrade(self, x, y , x2, y2):
        """Check whether a line goes around the east/west edge of the map"""

        directDist = sqrt(abs(x - x2) ** 2 + abs(y - y2) ** 2)
        xDistAcross = self.mapWidth - abs(x - x2)
        distAcross = sqrt(xDistAcross ** 2 + abs(y - y2) ** 2)

        return (distAcross < directDist)

if __name__ == "__main__":

    tv = TradeViz()
