from __future__ import annotations

import ctypes
from ctypes import wintypes


user32 = ctypes.WinDLL("user32", use_last_error=True)

if hasattr(wintypes, "ULONG_PTR"):
    ULONG_PTR = wintypes.ULONG_PTR
else:
    ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == ctypes.sizeof(ctypes.c_ulonglong) else ctypes.c_ulong

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_BACK = 0x08
VK_RETURN = 0x0D

user32.SendInput.argtypes = (wintypes.UINT, ctypes.c_void_p, ctypes.c_int)
user32.SendInput.restype = wintypes.UINT


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("value", INPUTUNION),
    ]


class KeyboardInjector:
    def type_text(self, text: str) -> None:
        if text:
            self._type_text(text)

    def finalize_session(self) -> None:
        return

    def _tap_vk(self, vk_code: int) -> None:
        down = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=vk_code, wScan=0, dwFlags=0, time=0, dwExtraInfo=0))
        up = INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(wVk=vk_code, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0),
        )
        self._send_inputs([down, up])

    def _type_text(self, text: str) -> None:
        for char in text:
            if char == "\n":
                self._tap_vk(VK_RETURN)
                continue

            scan_code = ord(char)
            down = INPUT(
                type=INPUT_KEYBOARD,
                ki=KEYBDINPUT(wVk=0, wScan=scan_code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0),
            )
            up = INPUT(
                type=INPUT_KEYBOARD,
                ki=KEYBDINPUT(
                    wVk=0,
                    wScan=scan_code,
                    dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                    time=0,
                    dwExtraInfo=0,
                ),
            )
            self._send_inputs([down, up])

    def _send_inputs(self, inputs: list[INPUT]) -> None:
        if not inputs:
            return
        count = len(inputs)
        array_type = INPUT * count
        input_array = array_type(*inputs)
        sent = user32.SendInput(count, ctypes.byref(input_array), ctypes.sizeof(INPUT))
        if sent != count:
            raise ctypes.WinError(ctypes.get_last_error())
