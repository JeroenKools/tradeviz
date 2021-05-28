"""
Created on 9 aug. 2015

@author: Jeroen Kools
"""

from src.TradeGrammar import begin, stop, eq, integer, name, quotedName, yesno, intList, floatList
from pyparsing import ZeroOrMore, OneOrMore, Optional, Literal, Each, Group


location = Literal("location").suppress() + eq + integer.setResultsName("location")
color = Literal("color") + eq + intList

nameLine = (Literal("name").suppress() + eq + quotedName)
path = (Literal("path") + eq + intList).suppress()
control = (Literal("control") + eq + floatList).suppress()
outgoing = Literal("outgoing") + eq + begin + \
     nameLine + path + Optional(control) + stop

member = Group(Literal("members") + eq + intList)
isEnd = Literal("end") + eq + yesno
isInland = Literal("inland") + eq + yesno
ai_will_propagate = Literal("ai_will_propagate_through_trade") + eq + yesno

node = Group(name.setResultsName("name") + eq + begin +
    Each([location,
          Optional(color),
          Optional(isInland),
          ZeroOrMore(outgoing),
          OneOrMore(member),
          Optional(isEnd),
          Optional(ai_will_propagate)
          ]) +
    stop)
nodes = OneOrMore(node)


if __name__ == "__main__":
    f = open(r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis IV\common\tradenodes\00_tradenodes.txt")
    txt = f.read()
    import tradeviz
    txt = tradeviz.remove_comments(txt)
    results = nodes.parseString(txt)

    nLocations = txt.count("location")
    nFound = len(results)

    print("Found %i out of %i tradenodes" % (nFound, nLocations))

#     for r in results:
#         print r["name"], r["location"]

