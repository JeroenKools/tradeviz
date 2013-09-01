'''
Trade Visualizer for EU4

Created on 21 aug. 2013

@author: Jeroen Kools
'''

# TODO: 'Nodes show' option: current value, local value, total trade power
# TODO: arrows ending at the edge of node circles
# TODO: Show countries option: ALL, specific tag
# TODO: better support for lower resolutions? (1280x720)

from TradeGrammar import tradeSection

import Tkinter as tk
import tkFileDialog
import tkMessageBox
from PIL import Image, ImageTk
import json
import _winreg

import time
import re
import os
from math import sqrt

provinceBMP = 'worldmap.gif'
EU4RegKey = "SOFTWARE\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Steam App 236850"

class TradeViz:
    def __init__(self):
        self.root = tk.Tk()
        self.paneHeight = 100
        self.w, self.h = self.root.winfo_screenwidth() - 15, self.root.winfo_screenheight() - self.paneHeight
        self.root.title("EU4 Trade Visualizer")
        self.root.iconbitmap('merchant.ico')

        img = Image.open(provinceBMP)
        self.mapWidth = img.size[0]
        img.thumbnail((self.w, self.h), Image.BICUBIC)
        self.mapThumbSize = img.size
        self.provinceImage = ImageTk.PhotoImage(img)

        self.setupGUI()

        self.tradenodes = []
        self.drawMap()
        self.root.grid_columnconfigure(1, weight=1)

        self.getConfig()

        self.root.focus_set()
        self.root.mainloop()

    def getConfig(self):

        if os.path.exists("tradeviz.cfg"):
            with open('tradeviz.cfg') as f:
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

    def getInstallDir(self):
        key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, EU4RegKey)
        try:
            i = 0
            while 1:
                name, val, typ = _winreg.EnumValue(key, i)
                if name == "InstallLocation":
                    self.config["installDir"] = val
                    break
                i += 1

        except WindowsError:
            pass

        if not 'installDir' in self.config or not os.path.exists(self.config["installDir"]):
            tkMessageBox.showerror("Error", "Europa Universalis installation could not be found! Please select your installation folder manually.")
            folder = tkFileDialog.askdirectory(initialdir="C:")
            if os.path.exists(os.path.join(folder, "eu4.exe")):
                self.config["installDir"] = folder

    def setupGUI(self):
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
        initialDir = '.'
        if "savefile" in self.config:
            initialDir = os.path.dirname(self.config["savefile"])

        filename = tkFileDialog.askopenfilename(filetypes=[("EU4 Saves", "*.eu4")], initialdir=initialDir)
        self.config["savefile"] = filename
        with open('tradeviz.cfg', 'w') as f:
            json.dump(self.config, f)

        self.saveEntry.delete(0, tk.END)
        self.saveEntry.insert(0, self.config["savefile"])

    def go(self, event=None):
        if self.config["savefile"]:
            self.getTradeData(self.config["savefile"])
            self.getNodeData()
            self.drawMap()

    def toggleShowZeroes(self, event=None):
        self.config["showZeroRoutes"] = self.showZeroVar.get()
        self.drawMap()
        with open('tradeviz.cfg', 'w') as f:
            json.dump(self.config, f)

    def exit(self, event=None):
        with open('tradeviz.cfg', 'w') as f:
            json.dump(self.config, f)
        self.root.quit()

    def getTradeData(self, savepath):
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

#         with open('tradeout.txt', 'w') as f:
#             f.write(str(result))

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
        # get all tradenode provinceIDs
        with open(self.tradenodesfile, 'r') as f:
            txt = f.read()
            tradenodes = re.findall(r"(\w+)=\s*{\s*location=(\d+)", txt)

        for i in range(len(tradenodes)):
            a, b = tradenodes[i]
            tradenodes[i] = (a, int(b))

        self.tradenodes = tradenodes
        assert tradenodes[0] == ('california', 871)

        # get all province locations
        with open(self.locationsfile, 'r') as f:
            txt = f.read()
            locations = re.findall(r"(\d+)=\s*{\s*position=\s*{\s*([\d\.]*)\s*([\d\.]*)", txt)

        for i in range(len(locations)):
            a, b, c = locations[i]

            locations[i] = (int(a), float(b), 2048 - float(c))

        self.provinceLocations = locations
        assert locations[0] == (1, 3085.0, 325.0)

    def drawMap(self):

        ratio = self.mapThumbSize[0] / float(self.mapWidth)
        self.root.geometry("%dx%d+0+0" % (self.w, self.mapThumbSize[1] + self.paneHeight))
        self.root.minsize(self.w, self.mapThumbSize[1] + self.paneHeight)
        self.root.maxsize(self.w, self.mapThumbSize[1] + self.paneHeight)
        self.canvas.create_image((0, 0), image=self.provinceImage, anchor=tk.NW)

        # draw incoming trade arrows
        for n, node in enumerate(self.tradenodes):
            x, y = self.getNodeLocation(n + 1)

            data = self.nodeData[node[0]]
            # print n + 1, node, data

            if 'incomingValue' in data:
                for i in range(len(data['incomingValue'])):
                    node2 = data['incomingFromNode'][i]
                    x2, y2 = self.getNodeLocation(node2)

                    lineWidth = int(10 * data['incomingValue'][i] / self.maxIncoming)
                    arrowShape = (max(10, lineWidth * 2), max(12, lineWidth * 2.5), max(5, lineWidth))

                    if data['incomingValue'][i] > 0:
                        linecolor = 'black'
                    else:
                        if self.showZeroVar.get() == 0:
                            continue
                        linecolor = 'yellow'

                    if not self.pacificTrade(x, y, x2, y2):

                        self.canvas.create_line((x * ratio , y * ratio , x2 * ratio , y2 * ratio),
                                width=lineWidth, arrow=tk.FIRST, arrowshape=arrowShape, fill=linecolor)

                        centerOfLine = ((x + x2) / 2 * ratio, (y + y2) / 2 * ratio)

                        self.canvas.create_text(centerOfLine, text=int(round(data['incomingValue'][i])), fill='white')

                    else:  # trade route crosses edge of map

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

                        self.canvas.create_text(centerOfLine, text=int(data['incomingValue'][i]), fill='white')

        # draw trade nodes and their current value
        for n, node in enumerate(self.tradenodes):
            x, y = self.getNodeLocation(n + 1)

            data = self.nodeData[node[0]]
            s = 5 + int(7 * data['currentValue'] / self.maxCurrent)

            self.canvas.create_oval((x * ratio - s, y * ratio - s, x * ratio + s, y * ratio + s), outline="red",
                                    fill="red")
            self.canvas.create_text((x * ratio, y * ratio), text=int(data['currentValue']), fill='white')

    def pacificTrade(self, x, y , x2, y2):
        directDist = sqrt(abs(x - x2) ** 2 + abs(y - y2) ** 2)
        xDistAcross = self.mapWidth - abs(x - x2)
        distAcross = sqrt(xDistAcross ** 2 + abs(y - y2) ** 2)

        return (distAcross < directDist)

if __name__ == "__main__":

    tv = TradeViz()
