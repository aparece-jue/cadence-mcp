"""Bounded Capture 24.1 DIB identity. Handles never cross the worker boundary."""
import ctypes
import hashlib
import re
import sys

MAX_DIB_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024


def native_handle(token):
    match = re.fullmatch(r'_([0-9a-fA-F]{16})_p_HGLOBAL', token)
    if ctypes.sizeof(ctypes.c_void_p) != 8 or not match:
        raise ValueError('Unsupported Capture HGLOBAL encoding')
    value = int.from_bytes(bytes.fromhex(match[1]), sys.byteorder)
    if not value:
        raise ValueError('Null Capture HGLOBAL')
    return value


def copy_dib(kernel, token, size):
    if type(size) is not int or not 0 < size <= MAX_DIB_BYTES:
        raise ValueError('DIB size limit')
    # This binding returns an allocated HGLOBAL value wrapper, not the DIB block.
    wrapper = native_handle(token)
    if kernel.GlobalSize(wrapper) != 8:
        raise ValueError('Unsupported Capture HGLOBAL wrapper')
    address = kernel.GlobalLock(wrapper)
    if not address:
        raise ValueError('Cannot lock Capture HGLOBAL wrapper')
    try:
        handle = int.from_bytes(ctypes.string_at(address, 8), sys.byteorder)
    finally:
        kernel.GlobalUnlock(wrapper)
    if not handle or not size <= kernel.GlobalSize(handle) <= 32 * 1024 * 1024:
        raise ValueError('DIB allocation bounds differ')
    address = kernel.GlobalLock(handle)
    if not address:
        raise ValueError('Cannot lock Capture DIB')
    try:
        return ctypes.string_at(address, size)
    finally:
        kernel.GlobalUnlock(handle)


class DibDigests:
    def __init__(self, kernel):
        self.kernel = kernel
        self.total = 0

    def digest(self, token, size):
        if type(size) is not int or not 0 < size <= MAX_DIB_BYTES:
            raise ValueError('DIB size limit')
        if self.total + size > MAX_TOTAL_BYTES:
            raise ValueError('Cumulative DIB read limit')
        blob = copy_dib(self.kernel, token, size)
        self.total += size
        return hashlib.sha256(blob).hexdigest()
