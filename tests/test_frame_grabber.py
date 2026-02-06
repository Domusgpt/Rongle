
import unittest
from unittest.mock import MagicMock, patch
import cv2
from rng_operator.visual_cortex.frame_grabber import FrameGrabber

class TestFrameGrabberNetwork(unittest.TestCase):
    @patch("cv2.VideoCapture")
    def test_open_local_device(self, mock_capture):
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_capture.return_value = mock_cap_instance

        grabber = FrameGrabber(device="/dev/video0")
        grabber.open()

        # Should use CAP_V4L2 for /dev/ devices
        mock_capture.assert_called_with("/dev/video0", cv2.CAP_V4L2)

    @patch("cv2.VideoCapture")
    def test_open_network_stream(self, mock_capture):
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_capture.return_value = mock_cap_instance

        grabber = FrameGrabber(device="http://192.168.1.100:8080/video")
        grabber.open()

        # Should use CAP_FFMPEG for http:// URLs
        mock_capture.assert_called_with("http://192.168.1.100:8080/video", cv2.CAP_FFMPEG)

    @patch("cv2.VideoCapture")
    def test_open_rtsp_stream(self, mock_capture):
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_capture.return_value = mock_cap_instance

        grabber = FrameGrabber(device="rtsp://admin:pass@192.168.1.100/stream")
        grabber.open()

        # Should use CAP_FFMPEG for rtsp:// URLs
        mock_capture.assert_called_with("rtsp://admin:pass@192.168.1.100/stream", cv2.CAP_FFMPEG)

    @patch("cv2.VideoCapture")
    def test_open_unknown_device(self, mock_capture):
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_capture.return_value = mock_cap_instance

        grabber = FrameGrabber(device=0)
        grabber.open()

        # Should default to CAP_ANY
        mock_capture.assert_called_with(0, cv2.CAP_ANY)

if __name__ == "__main__":
    unittest.main()
