import unittest

from gui import widgets


class ViewerResampleTests(unittest.TestCase):
    def test_smooth_zoom_uses_nearest_during_interactive_zoom_in(self):
        resample = widgets._viewer_resample(
            fast_zoom=False,
            smooth_zoom=True,
            zoom=2.0,
            interactive=True,
        )

        self.assertEqual(resample, widgets.Image.Resampling.NEAREST)

    def test_smooth_zoom_uses_bilinear_when_settled(self):
        resample = widgets._viewer_resample(
            fast_zoom=False,
            smooth_zoom=True,
            zoom=2.0,
            interactive=False,
        )

        self.assertEqual(resample, widgets.Image.Resampling.BILINEAR)

    def test_smooth_zoom_keeps_bilinear_while_zoomed_out(self):
        resample = widgets._viewer_resample(
            fast_zoom=False,
            smooth_zoom=True,
            zoom=0.5,
            interactive=True,
        )

        self.assertEqual(resample, widgets.Image.Resampling.BILINEAR)


if __name__ == "__main__":
    unittest.main()
