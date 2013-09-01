'''
Created on 31 aug. 2013

@author: Jeroen
'''

from pyparsing import Literal, Word, alphas, OneOrMore
from TradeGrammar import eq, begin, quote, stop, flt, integer

comment = Literal("#") + Word(alphas + " _").suppress()

positions = Literal("position") + eq + begin + OneOrMore(flt) + stop.setResultsName("positions", True)
rotations = Literal("rotation") + eq + begin + OneOrMore(flt) + stop
heights = Literal("height") + eq + begin + OneOrMore(flt) + stop

provincePosition = comment + integer + eq + begin + positions + rotations.suppress() + heights.suppress() + stop
