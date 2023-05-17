import sys
import os
import logging

WinRegKey =\
    "S-1-5-21-1472195844-1040877506-3863951423-1002\\System\\GameConfigStore\\Children\\" +\
    "bcc6609b-312a-4db7-b935-9a8da514ba49"
MacDefaultPath = os.path.expanduser("~/Library/Application Support/Steam/Steamapps/common/Europa Universalis IV")
LinuxDefaultPath = os.path.expanduser("~/.local/share/Steam/SteamApps/common/Europa Universalis IV")


def getInstallDir():
    if sys.platform == "win32":
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_USERS, WinRegKey)
            i = 0
            while 1:
                quotedName, val, _type = winreg.EnumValue(key, i)
                if quotedName == "MatchedExeFullPath":
                    logging.info("Found install dir in Windows registry: %s" % val)
                    return os.path.dirname(val)
                i += 1
        except WindowsError as e:
            logging.error("Error while trying to find install dir in Windows registry: %s" % e)
            raise e

    elif sys.platform == "darwin":  # OS X

        if os.path.exists(MacDefaultPath):
            return MacDefaultPath

    else:  # Assume it's Linux
        if os.path.exists(LinuxDefaultPath):
            return LinuxDefaultPath


def removeComments(txt):
    lines = txt.split("\n")
    for i in range(len(lines)):
        lines[i] = lines[i].split("#")[0]
    return "\n".join(lines)
