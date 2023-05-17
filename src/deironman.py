"""
Created on May 10, 2017

@author: Jeroen Kools
"""

import os

testFileDir = os.path.expanduser(R"D:\Documents\Paradox Interactive\Europa Universalis IV\save games")

substitutions = {
    b"\x00\x00": b"",
    b"\x01\x00": b"=",
    b"\x03\x00": b"{\n",
    b"\x04\x00": b"}\n",

    # data types
    b"\x0c\x00": b"(int)",
    b"\x0d\x00": b"(float)",
    b"\x0e\x00": b"(bool)",
    b"\x0f\x00": b"(string)",
    b"\x14\x00": b"(string)",
    b"\x17\x00": b"(string)",

    # save metadata
    b"\x69\x2c": b"date",
    b"\xe1\x2e": b"dlc_enabled",

    b"\x5e\x01": b"node",
    b"\x71\x28": b"trade",
    b"\x35\x28": b"definitions",

    b"\x09\x2C": b"has_trader",
    b"\xad\x2c": b"current",
    b"\xa8\x2a": b"outgoing",

    b"\xA0\x02D": b"trade_power",
    b"\xA2\x2D": b"province_trade_power_value",
    b"\xA5\x2D": b"local_value",
    b"\xA6\x2D": b"retention",
    b"\xA7\x2D": b"steer_power",
    b"\xA8\x2D": b"pull_power",
    b"\xA9\x2D": b"retain_power",
    b"\xAA\x2D": b"highest_power",
    b"\xAB\x2D": b"max_power",
    b"\xAC\x2D": b"province_power",
    b"\xAD\x2D": b"power_fraction",
    b"\xAE\x2D": b"power_fraction_push",
}


def deironman(txt):
    for pattern, replacement in substitutions.items():
        txt = txt.replace(pattern, replacement)
    return txt


if __name__ == '__main__':
    for fn in os.listdir(testFileDir):
        with open(os.path.join(testFileDir, fn), "rb") as f:
            try:
                txt = f.read()
                print(f"{fn: <40} {deironman(txt[:150])}")
            except UnicodeDecodeError:
                print(fn, "UnicodeDecodeError")
