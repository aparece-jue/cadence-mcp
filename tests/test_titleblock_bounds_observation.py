import copy
import unittest

from cadence_mcp.capture_titleblock_fields import normalize_bounds
from cadence_mcp.core import CadenceError


class TitleblockBoundsObservation(unittest.TestCase):
    def row(self):
        return dict(localBounds=[0, 0, 0, 0], symbolBounds=[0, 0, 0, 0],
                    offsetBounds=[200, 200, 200, 200], dirty=1)

    def test_dirty_degenerate_success_is_not_verified_geometry(self):
        row = self.row()
        result = normalize_bounds(row)
        self.assertEqual(result['cacheStatus'], 'dirty_cache')
        self.assertTrue(result['degenerate'])
        self.assertFalse(result['renderedBoundsVerified'])
        self.assertEqual(row, self.row())

    def test_clean_cache_does_not_certify_rendering(self):
        row = self.row()
        row['dirty'] = 0
        self.assertEqual(normalize_bounds(row)['cacheStatus'], 'degenerate_cache')
        row.update(localBounds=[-10, -20, 30, 40], symbolBounds=[-10, -20, 30, 40],
                   offsetBounds=[190, 180, 230, 240])
        result = normalize_bounds(row)
        self.assertEqual(result['cacheStatus'], 'clean_cache_unverified')
        self.assertFalse(result['degenerate'])
        self.assertFalse(result['renderedBoundsVerified'])

    def test_bad_worker_document_rejected(self):
        for key, value in [('dirty', True), ('dirty', 2), ('localBounds', [0]*3),
                           ('offsetBounds', [0, False, 1, 2]),
                           ('symbolBounds', [0, 0, 2**31, 2])]:
            row = self.row()
            row[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(CadenceError):
                normalize_bounds(row)
        for row in [None, {k: v for k, v in self.row().items() if k != 'dirty'},
                    dict(self.row(), extra=0)]:
            with self.assertRaises(CadenceError):
                normalize_bounds(copy.deepcopy(row))
