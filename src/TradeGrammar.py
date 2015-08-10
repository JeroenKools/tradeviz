from pyparsing import ZeroOrMore, OneOrMore, Optional, Literal, Word, alphas, nums

'''
Created on 31 aug. 2013

Pyparsing grammar describing the trade section of EU4 save files

@author: Jeroen Kools
'''


# Terminals
eq = Literal("=").suppress()
begin = Literal("{").suppress()
stop = Literal("}").suppress()
quote = Literal('"').suppress()

name = Word(alphas, alphas + nums + "_")
quotedName = quote + name + quote
yesno = Literal("yes") | Literal("no")
flt = Word(nums + ".-").setParseAction(lambda s, l, t: float(t[0]))
integer = Word(nums + "-").setParseAction(lambda s, l, t: int(t[0]))
intList = begin + OneOrMore(integer) + stop
floatList = begin + OneOrMore(flt) + stop

definitionsLine = Literal("definitions").suppress() + eq + quotedName.setResultsName("quotedName")
currentLine = Literal("current").suppress() + eq + flt.setResultsName("currentValue")
localValueLine = Literal("local_value").suppress() + eq + flt.setResultsName("localValue")
outgoingLine = Literal("outgoing").suppress() + eq + flt.setResultsName("outgoing")
valueAddedOutgoingLine = (Literal("value_added_outgoing") + eq + flt).suppress()
retentionLine = (Literal("retention") + eq + flt).suppress()
steerPowerLine = (Literal("steer_power") + eq + flt).suppress()
totalLine = (Literal("total").suppress() + eq + flt).suppress()  # total trade power
provincePower = Word("p_pow") ^ Word("province_power")
provincePowerLine = (provincePower + eq + flt).suppress()
maxLine = (Literal("max") + eq + flt).suppress()
collectorPowerLine = (Literal("collector_power") + eq + flt).suppress()
pullPowerLine = (Literal("pull_power") + eq + flt).suppress()
retainPowerLine = (Literal("retain_power") + eq + flt).suppress()
highestPowerLine = (Literal("highest_power") + eq + flt).suppress()
pirateHuntLine = (Literal("pirate_hunt") + eq + flt).suppress()
valueLine = Literal("value").suppress() + eq + flt.setResultsName("incomingValue", True)
fromLine = Literal("from").suppress() + eq + integer.setResultsName("incomingFromNode", True)

countryLine = Literal("country") + eq + quotedName
prevLine = Literal("prev") + eq + flt
maxPowerLine = Literal("max_power") + eq + flt
shipPowerLine = Literal("ship_power") + eq + flt
powerFractionLine = Literal("power_fraction") + eq + flt
powerFractionPushLine = Literal("power_fraction_push") + eq + flt
moneyLine = Literal("money") + eq + flt
typeLine = Literal("type") + eq + integer
actualAddedValueLine = Literal("actual_added_value").suppress() + eq + flt
hasTraderLine = Literal("has_trader") + eq + yesno
hasCapitalLine = Literal("has_capital") + eq + yesno
hasSubjectLine = Literal("has_subject") + eq + yesno

modifierSection = Literal("modifier") + eq + begin + \
        Literal("key") + eq + quotedName + \
        Literal("duration") + eq + integer + \
        Literal("power") + eq + flt + stop

lightShipLine = Literal("light_ship").suppress() + eq + integer
transferredOutLine = Literal("transferred_out").suppress() + eq + flt
transferredInLine = Literal("transferred_in").suppress() + eq + flt
transferredFromIndexSection = Literal("transfered_from_index").suppress() + eq + intList
transferredFromValueSection = Literal("transfered_from_value").suppress() + eq + floatList
transferredToIndexSection = Literal("transfered_to_index").suppress() + eq + intList
transferredToValueSection = Literal("transfered_to_value").suppress() + eq + floatList
privateerMissionLine = Literal("privateer_mission").suppress() + eq + flt

powerSection = Literal("power").suppress() + eq + begin + \
                (
                    countryLine +
                    currentLine +
                    Optional(prevLine) +
                    maxPowerLine +
                    provincePowerLine +
                    shipPowerLine +
                    Optional(privateerMissionLine) +
                    powerFractionLine +
                    powerFractionPushLine +
                    moneyLine +
                    totalLine +
                    steerPowerLine +
                    typeLine +
                    actualAddedValueLine +
                    hasTraderLine +
                    hasCapitalLine +
                    Optional(hasSubjectLine) +
                    Optional(lightShipLine) +
                    Optional(transferredOutLine) +
                    Optional(transferredInLine) +
                    Optional(transferredToIndexSection) +
                    Optional(transferredToValueSection) +
                    Optional(transferredFromIndexSection) +
                    Optional(transferredFromValueSection) +
                    Optional(modifierSection)
                ) + stop

valLine = Literal("val") + eq + flt
maxPowLine = Literal("max_pow") + eq + flt
maxDemandLine = Literal("max_demand") + eq + flt
addLine = Literal("add") + eq + flt
tInLine = Literal("t_in") + eq + flt
tOutLine = Literal("t_out") + eq + flt
tFromSection = Literal("t_from") + eq + begin + OneOrMore(name + eq + flt) + stop
tToSection = Literal("t_to") + eq + begin + OneOrMore(name + eq + flt) + stop

# new (AOW or ED?) format for a country's power in a node
countryPowerSection = name + eq + begin + \
                    (
                       typeLine +
                       Optional(valLine) +
                       Optional(prevLine) +
                       Optional(maxPowLine) +
                       maxDemandLine +
                       Optional(provincePowerLine) +
                       Optional(shipPowerLine) +
                       Optional(powerFractionLine) +
                       Optional(moneyLine) +
                       Optional(totalLine) +
                       Optional(steerPowerLine) +
                       Optional(addLine) +
                       Optional(hasTraderLine) +
                       Optional(hasCapitalLine) +
                       Optional(lightShipLine) +
                       Optional(tOutLine) +
                       Optional(tInLine) +
                       Optional(tToSection) +
                       Optional(tFromSection) +
                       Optional(modifierSection)
                    ) + stop

tradegoodSection = Literal("trade_goods_size").suppress() + eq + begin + \
    OneOrMore(flt) + stop

incomingSection = (Literal("incoming").suppress() + eq + begin + \
    actualAddedValueLine + valueLine + fromLine + stop)

newIncomingSection = (Literal("incoming").suppress() + eq + begin +
                        addLine + valueLine + fromLine + stop)

topProvincesSection = Literal("top_provinces").suppress() + eq + begin + OneOrMore(quotedName | name) + stop
topProvincesValuesSection = Literal("top_provinces_values").suppress() + eq + floatList
topPowerSection = Literal("top_power").suppress() + eq + begin + OneOrMore(quotedName | name) + stop
topPowerValuesSection = Literal("top_power_values").suppress() + eq + floatList
tradeCompanyRegionLine = Literal("trade_company_region").suppress() + eq + yesno

nodeSection = (Literal("node").suppress() + eq + begin + \
                definitionsLine +
                currentLine +
                localValueLine +
                outgoingLine +
                valueAddedOutgoingLine +
                retentionLine +
                ZeroOrMore(steerPowerLine) +
                totalLine +
                Optional(provincePowerLine) +
                maxLine +
                collectorPowerLine +
                pullPowerLine +
                retainPowerLine +
                highestPowerLine +
                Optional(pirateHuntLine) +
                ZeroOrMore(powerSection) +
                ZeroOrMore(countryPowerSection) +
                ZeroOrMore(incomingSection) +
                ZeroOrMore(newIncomingSection) +
                Optional(tradegoodSection) + # Western Europe has no trade goods!
                Optional(topProvincesSection) +
                Optional(topProvincesValuesSection) +
                Optional(topPowerSection) +
                Optional(topPowerValuesSection) +
                Optional(tradeCompanyRegionLine) +
                stop).setResultsName("Nodes", True)

tradeSection = begin + OneOrMore(nodeSection) + stop
