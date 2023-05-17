"""
Created on 9 aug. 2015

Pyparsing grammar describing the structure of the EU4 file 00_tradenodes.txt

@author: Jeroen Kools
"""

import os.path

from pyparsing import ZeroOrMore, OneOrMore, Optional, Literal, Each, Group

from TradeGrammar import begin, stop, eq, integer, name, quotedName, yesno, intList, floatList
import util

location = Literal("location").suppress() + eq + integer.setResultsName("location")
color = Literal("color") + eq + intList

nameLine = (Literal("name").suppress() + eq + quotedName)
path = (Literal("path") + eq + intList).suppress()
control = (Literal("control") + eq + floatList).suppress()
outgoing = Literal("outgoing") + eq + begin + \
           nameLine + path + Optional(control) + stop

member = Group(Literal("members") + eq + intList)
aiWillPropagate = Literal("ai_will_propagate_through_trade") + eq + yesno
isEnd = Literal("end") + eq + yesno
isInland = Literal("inland") + eq + yesno

node = Group(name.setResultsName("name") + eq + begin +
             Each([location,
                   Optional(color),
                   Optional(isInland),
                   ZeroOrMore(outgoing),
                   OneOrMore(member),
                   Optional(isEnd),
                   Optional(aiWillPropagate)
                   ]
                  ) +
             stop)
nodes = OneOrMore(node)

if __name__ == "__main__":
    installDir = util.search_install_dir()
    tradeNodesTextPath = os.path.join(installDir, R"common\tradenodes\00_tradenodes.txt")
    print("Looking for trade nodes definitions file at", repr(tradeNodesTextPath))
    with open(tradeNodesTextPath) as f:
        txt = f.read()
        txt = util.remove_comments(txt)
        results = nodes.parseString(txt)
        nLocations = txt.count("location")
        nFound = len(results)

    print(f"Found {nFound} out of {nLocations} trade nodes")

    for r in results:
        print(r["name"], r["location"])
