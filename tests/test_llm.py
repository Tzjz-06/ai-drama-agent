import unittest

from ai_drama_agent.llm import _parse_json_object


class JsonResponseParsingTests(unittest.TestCase):
    def test_parses_json_wrapped_in_provider_text(self) -> None:
        content = '生成完成：\n```json\n{"title":"测试","ok":true}\n```\n请查收。'

        parsed = _parse_json_object(content, "模型")

        self.assertEqual(parsed, {"title": "测试", "ok": True})

    def test_accepts_bom_and_unescaped_line_break_in_string(self) -> None:
        content = '\ufeff{"content":"第一行\n第二行"}'

        parsed = _parse_json_object(content, "模型")

        self.assertEqual(parsed["content"], "第一行\n第二行")

    def test_reports_truncated_json(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "内容不完整.*上游供应商可能截断"):
            _parse_json_object('{"content":"未结束', "模型")


if __name__ == "__main__":
    unittest.main()
