"""AI 条文分析输出的纯文本格式测试。"""

from app.services.ai_service import clean_analysis_output


def test_clean_analysis_output_removes_markdown_and_long_dash_separators():
    raw = "## **核心含义：**\n* 病机——症状相互影响。\n---\n`辨证要点`：注意寒热。"

    result = clean_analysis_output(raw)

    assert result == "核心含义：\n病机，症状相互影响。\n\n辨证要点：注意寒热。"
    assert "*" not in result
    assert "——" not in result
    assert "---" not in result


def test_clean_analysis_output_keeps_plain_chinese_and_paragraphs():
    raw = "核心含义：说明病机。\n\n\n临床应用：结合症状判断。"

    assert clean_analysis_output(raw) == "核心含义：说明病机。\n\n临床应用：结合症状判断。"
