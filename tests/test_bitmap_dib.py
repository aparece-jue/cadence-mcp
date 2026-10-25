import ctypes
import hashlib
import sys
import unittest
from unittest.mock import patch

from cadence_mcp.bitmap_dib import DibDigests, copy_dib, native_handle, MAX_DIB_BYTES, MAX_TOTAL_BYTES
from cadence_mcp.embedded_tcl import command
from cadence_mcp.library_vector_query import validate_descriptor


class Kernel:
    def __init__(self):
        self.payload = ctypes.create_string_buffer(b'actual DIB pixels')
        self.handle = ctypes.addressof(self.payload)
        self.wrapper = ctypes.create_string_buffer(self.handle.to_bytes(8, sys.byteorder))
        self.box = ctypes.addressof(self.wrapper)
        self.token = '_' + self.box.to_bytes(8, sys.byteorder).hex() + '_p_HGLOBAL'
        self.unlocked = []
        self.sizes = {self.box: 8, self.handle: 18}
        self.lock_fail = None

    def GlobalSize(self, handle):
        return self.sizes.get(handle, 0)

    def GlobalLock(self, handle):
        return 0 if handle == self.lock_fail else handle

    def GlobalUnlock(self, handle):
        self.unlocked.append(handle)
        return 0


class BitmapDibTests(unittest.TestCase):
    def test_complete_bytes_and_unlocks(self):
        kernel = Kernel()
        expected = b'actual DIB pixels'
        self.assertEqual(copy_dib(kernel, kernel.token, len(expected)), expected)
        self.assertEqual(kernel.unlocked, [kernel.box, kernel.handle])
        digests = DibDigests(kernel)
        self.assertEqual(digests.digest(kernel.token, len(expected)), hashlib.sha256(expected).hexdigest())
        self.assertEqual(digests.total, len(expected))

    def test_only_validated_binding_encoding(self):
        for token in ['0x1234','1234','_0100000000000000_p_CPoint','_00_p_HGLOBAL','_0000000000000000_p_HGLOBAL']:
            with self.subTest(token=token), self.assertRaises(ValueError):
                native_handle(token)

    def test_size_limits_precede_native_access(self):
        for size in [0,-1,True,MAX_DIB_BYTES+1,'16']:
            with self.subTest(size=size), self.assertRaises(ValueError):
                copy_dib(None, 'not-a-handle', size)
        digests = DibDigests(None)
        digests.total = MAX_TOTAL_BYTES
        with self.assertRaises(ValueError):
            digests.digest('not-a-handle', 1)

    def test_wrapper_and_data_capacity_fail_closed(self):
        for box_size, data_size in [(7,18),(8,2),(8,32*1024*1024+1)]:
            kernel = Kernel()
            kernel.sizes = {kernel.box:box_size,kernel.handle:data_size}
            with self.subTest(box_size=box_size,data_size=data_size), self.assertRaises(ValueError):
                copy_dib(kernel,kernel.token,16)
            self.assertNotIn(kernel.handle,kernel.unlocked)

    def test_lock_failure_and_copy_failure_release(self):
        kernel = Kernel()
        kernel.lock_fail = kernel.handle
        with self.assertRaises(ValueError):
            copy_dib(kernel,kernel.token,16)
        self.assertEqual(kernel.unlocked,[kernel.box])
        kernel = Kernel()
        original = ctypes.string_at
        def fail_payload(address,count):
            if address == kernel.handle:
                raise ValueError('copy refused')
            return original(address,count)
        with patch('cadence_mcp.bitmap_dib.ctypes.string_at',side_effect=fail_payload), self.assertRaises(ValueError):
            copy_dib(kernel,kernel.token,16)
        self.assertEqual(kernel.unlocked,[kernel.box,kernel.handle])

    def test_bitmap_descriptor_validation(self):
        good=['bitmap',[0,0,20,20],[0,0],[2,2],56,'0'*64]
        self.assertEqual(validate_descriptor(good),good)
        for index,value in [(1,[0,0,20]),(2,[False,0]),(3,[0,2]),(4,MAX_DIB_BYTES+1),(4,True),(5,'x'*64),(5,'A'*64)]:
            altered=good.copy();altered[index]=value
            with self.subTest(index=index,value=value), self.assertRaises(ValueError):
                validate_descriptor(altered)

    def test_internal_reader_allowlist(self):
        with self.assertRaises(ValueError):
            command('C:/install','arbitrary.tcl',[])
        argv=command('C:/install','inspect_library_vectors.tcl',['x; [exit]','中文'])
        self.assertEqual(argv[-2:],['x; [exit]','中文'])
        self.assertIn('cadence_mcp.embedded_tcl',argv)


if __name__ == '__main__':
    unittest.main()
