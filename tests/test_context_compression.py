import unittest

from ai_drama_agent.context_compression import ForgettingCurveCompressor


class ForgettingCurveCompressionTests(unittest.TestCase):
    def test_short_context_is_left_untouched(self) -> None:
        source = "标题：雨夜来信\n\n正文：林默拆开信封。"

        result = ForgettingCurveCompressor(max_chars=256).compress(source, query="信封")

        self.assertEqual(result.text, source)
        self.assertFalse(result.compressed)
        self.assertEqual(result.retained_ratio, 1.0)

    def test_long_context_keeps_anchors_and_respects_budget(self) -> None:
        blocks = [
            "标题：雨夜来信",
            "第一章：林默收到来自未来的信，信封边缘有蓝色蜡封。",
            "第二章：城市进入停电状态，旧车站成为调查地点。",
            "第三章：林默在车站找到一枚带划痕的铜钥匙。",
            "第四章：他回到办公室，决定追查寄信人的身份。",
            "背景记录：" + "无关的城市噪声。" * 20,
            "当前章：林默展开信纸，准备回答最后一个问题。",
        ]
        source = "\n\n".join(blocks)

        result = ForgettingCurveCompressor(max_chars=256).compress(source, query="铜钥匙")

        self.assertTrue(result.compressed)
        self.assertLessEqual(result.compressed_chars, 256)
        self.assertIn("标题：雨夜来信", result.text)
        self.assertIn("当前章：林默展开信纸", result.text)
        self.assertIn("铜钥匙", result.text)
        self.assertLess(result.retained_ratio, 1.0)

    def test_relevance_can_retain_an_older_block(self) -> None:
        source = "\n\n".join(
            [
                "项目锚点：雨夜来信",
                "无关的城市新闻和天气记录。",
                "无关的办公室日常记录。",
                "无关的档案摘要。" * 20,
                "当前状态：林默等待下一步行动。",
            ]
        )

        result = ForgettingCurveCompressor(max_chars=256).compress(source, query="办公室")

        self.assertIn("办公室", result.text)


if __name__ == "__main__":
    unittest.main()
