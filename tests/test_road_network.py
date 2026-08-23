import unittest

from engine.core import road_network as R


def snapshot(net):
    return {
        "big_rows": sorted(net["big_rows"]),
        "big_cols": sorted(net["big_cols"]),
        "big_rows_ext": sorted(net["big_rows_ext"].items()),
        "big_cols_ext": sorted(net["big_cols_ext"].items()),
        "small_rows": sorted(net["small_rows"]),
        "small_cols": sorted(net["small_cols"]),
        "small_rows_ext": sorted(net["small_rows_ext"].items()),
        "small_cols_ext": sorted(net["small_cols_ext"].items()),
        "road_cells": sorted(net["road_cells"]),
    }


class RoadNetworkTests(unittest.TestCase):
    def test_seeded_generation_is_stable(self):
        size = R.make_size(40, even=True)
        first = snapshot(R.gen_networks(17, size=size))
        second = snapshot(R.gen_networks(17, size=size))
        different = snapshot(R.gen_networks(18, size=size))

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)


if __name__ == "__main__":
    unittest.main()
