import unittest

from gui import pan_zoom


class ViewerResampleTests(unittest.TestCase):
    def test_smooth_zoom_uses_nearest_during_interactive_zoom_in(self):
        resample = pan_zoom.viewer_resample(
            fast_zoom=False,
            smooth_zoom=True,
            zoom=2.0,
            interactive=True,
        )

        self.assertEqual(resample, pan_zoom.Image.Resampling.NEAREST)

    def test_smooth_zoom_uses_bilinear_when_settled(self):
        resample = pan_zoom.viewer_resample(
            fast_zoom=False,
            smooth_zoom=True,
            zoom=2.0,
            interactive=False,
        )

        self.assertEqual(resample, pan_zoom.Image.Resampling.BILINEAR)

    def test_smooth_zoom_keeps_bilinear_while_zoomed_out(self):
        resample = pan_zoom.viewer_resample(
            fast_zoom=False,
            smooth_zoom=True,
            zoom=0.5,
            interactive=True,
        )

        self.assertEqual(resample, pan_zoom.Image.Resampling.BILINEAR)


if __name__ == "__main__":
    unittest.main()
