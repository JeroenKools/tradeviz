import sys
import os
import logging
import tkinter as tk
import tkinter.messagebox

win_reg_key =\
    "S-1-5-21-1472195844-1040877506-3863951423-1002\\System\\GameConfigStore\\Children\\" +\
    "bcc6609b-312a-4db7-b935-9a8da514ba49"
mac_default_path = os.path.expanduser("~/Library/Application Support/Steam/Steamapps/common/Europa Universalis IV")
linux_default_path = os.path.expanduser("~/.local/share/Steam/SteamApps/common/Europa Universalis IV")


def search_install_dir():
    if sys.platform == "win32":
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_USERS, win_reg_key)
            i = 0
            while 1:
                quoted_name, val, _type = winreg.EnumValue(key, i)
                if quoted_name == "MatchedExeFullPath":
                    logging.info("Found install dir in Windows registry: %s" % val)
                    return os.path.dirname(val)
                i += 1
        except WindowsError as e:
            logging.error("Error while trying to find install dir in Windows registry: %s" % e)
            raise e

    elif sys.platform == "darwin":  # OS X

        if os.path.exists(mac_default_path):
            return mac_default_path

    else:  # Assume it's Linux
        if os.path.exists(linux_default_path):
            return linux_default_path


def remove_comments(txt):
    lines = txt.split("\n")
    for i in range(len(lines)):
        lines[i] = lines[i].split("#")[0]
    return "\n".join(lines)


def sign(v):
    if v < 0:
        return -1
    else:
        return 1


def show_error(log_message, user_message):
    if not user_message:
        user_message = log_message
    logging.error(f"{user_message}\n{log_message}")
    tk.messagebox.showerror("Error", user_message)
