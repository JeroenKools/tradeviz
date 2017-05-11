'''
Created on May 10, 2017

@author: Jeroen Kools
'''

testFilePath = r"C:\Users\jakestauch\Documents\Paradox Interactive\Europa Universalis IV\save games\Ottos1.13\Ottos1.13.eu4"

substitutions = {
    "\x00\x00":"",
    "\x01\x00":"=",
    "\x03\x00":"{\n",
    "\x04\x00":"}\n",

    # data types
    "\x0c\x00":"(int)",
    "\x0d\x00":"(float)",
    "\x0e\x00":"(bool)",
    "\x0f\x00":"(string)",
    "\x14\x00":"(string)",
    "\x17\x00":"(string)",

    # save metadata
    "\x69\x2c":"date",
    "\xe1\x2e":"dlc_enabled",

    "\x5e\x01":"node",
    "\x71\x28":"trade",
    "\x35\x28":"definitions",

    "\x09\x2C":"has_trader",
    "\xad\x2c":"current",
    "\xa8\x2a":"outgoing",

    "\xA0\x02D":"trade_power",
    "\xA2\x2D":"province_trade_power_value",
    "\xA5\x2D":"local_value",
    "\xA6\x2D":"retention",
    "\xA7\x2D":"steer_power",
    "\xA8\x2D":"pull_power",
    "\xA9\x2D":"retain_power",
    "\xAA\x2D":"highest_power",
    "\xAB\x2D":"max_power",
    "\xAC\x2D":"province_power",
    "\xAD\x2D":"power_fraction",
    "\xAE\x2D":"power_fraction_push",
}


def deironman(txt):
    for pattern, replacement in substitutions.items():
        txt = txt.replace(pattern, replacement)
    return txt

if __name__ == '__main__':
    txt = ""
    with open(testFilePath) as f:
        txt = f.read()

        print deironman(txt[:1500])
