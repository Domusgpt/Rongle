import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from pathlib import Path
import os
import shutil
from training.llm_labeler import LLMLabeler

class TestAsyncLabelerFix(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = Path("test_dataset_fix")
        self.labeler = LLMLabeler(api_key="fake", dataset_dir=str(self.test_dir))

    async def asyncTearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch("training.llm_labeler.LLMLabeler._call_vlm", new_callable=AsyncMock)
    async def test_label_frame_saves_image_async(self, mock_call_vlm):
        # Mock VLM response
        mock_call_vlm.return_value = '{"screen_type": "browser", "elements": []}'

        image_bytes = b"fake image data"
        width, height = 100, 100

        # Call label_frame
        frame = await self.labeler.label_frame(image_bytes, width, height, save_image=True)

        # Verify result
        self.assertTrue(Path(frame.image_path).exists())
        self.assertEqual(Path(frame.image_path).read_bytes(), image_bytes)
        self.assertEqual(frame.width, width)
        self.assertEqual(frame.height, height)

        # Ensure it works without save_image too
        frame2 = await self.labeler.label_frame(image_bytes, width, height, save_image=False)
        self.assertEqual(frame2.image_path, "")

if __name__ == "__main__":
    unittest.main()
