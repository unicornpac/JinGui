"""
解析器回归测试 —— 以《伤寒论》398条 DOCX 作为 golden sample。

每次修改解析器后必须通过此测试。
验收标准：
- 条号覆盖 1–398
- 正文不含开头罗马数字（Ⅰ~Ⅹ）
- 正文不含末尾（数字）
- 已知样本第 9、10、11、12 条正文完全一致
- 章节边界正确
- 重复号问题被报告，不会静默导入
"""
import os
import pytest

# 测试用的 DOCX 文件路径
_SHANGHAN_DOCX = os.path.join(
    os.path.dirname(__file__), "..", "uploads", "20260801_165919_伤寒论原文398条整理.docx"
)

# 跳过条件：DOCX 文件不存在时跳过
pytestmark = pytest.mark.skipif(
    not os.path.exists(_SHANGHAN_DOCX),
    reason="测试 DOCX 文件不存在"
)


@pytest.fixture(scope="module")
def parsed_articles():
    """解析 DOCX，返回条文列表"""
    from app.services.parser import DocumentParser

    parser = DocumentParser()
    result = parser.parse(_SHANGHAN_DOCX)
    content = result.get("content", "")
    paragraphs = result.get("paragraphs", [])

    extracted = parser.extract_texts_and_cases(
        content,
        filename=os.path.basename(_SHANGHAN_DOCX),
        paragraphs=paragraphs,
    )
    return extracted.get("texts", [])


class TestArticleCoverage:
    """条号覆盖测试"""

    def test_all_398_numbers_present(self, parsed_articles):
        """验证条号 1-398 全覆盖，无缺失"""
        nums = {t["article_number"] for t in parsed_articles if t.get("article_number")}
        missing = sorted(set(range(1, 399)) - nums)
        assert len(missing) == 0, f"缺失条号: {missing}"

    def test_no_extra_numbers(self, parsed_articles):
        """验证条号不超过 398"""
        nums = [t["article_number"] for t in parsed_articles if t.get("article_number")]
        extra = [n for n in nums if n > 398]
        assert len(extra) == 0, f"超出范围的条号: {extra}"


class TestContentCleaning:
    """正文清理测试"""

    def test_no_roman_numerals_in_content(self, parsed_articles):
        """正文不应包含罗马数字 I-V"""
        roman_chars = set("ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ")
        offenders = []
        for t in parsed_articles:
            if any(ch in t["content"] for ch in roman_chars):
                offenders.append(t["article_number"])
        assert len(offenders) == 0, f"正文含罗马数字的条号: {offenders}"

    def test_no_sentence_end_number_in_content(self, parsed_articles):
        """正文末尾不应包含 （数字）标记"""
        import re
        offenders = []
        for t in parsed_articles:
            if re.search(r"[（(]\d+[）)]\s*$", t["content"]):
                offenders.append(t["article_number"])
        assert len(offenders) == 0, f"正文含末尾条号的条号: {offenders}"

    def test_content_not_empty(self, parsed_articles):
        """所有正文非空"""
        empty = [t["article_number"] for t in parsed_articles
                 if not t.get("content") or len(t["content"].strip()) < 5]
        assert len(empty) == 0, f"空正文条号: {empty}"


class TestKnownSamples:
    """已知样本验证"""

    def test_article_9_exact_match(self, parsed_articles):
        """第 9 条: 太阳病欲解时，从巳至未上。"""
        a9 = _find_article(parsed_articles, 9)
        assert a9 is not None, "第 9 条缺失"
        assert a9["content"] == "太阳病欲解时，从巳至未上。"

    def test_article_10_exact_match(self, parsed_articles):
        """第 10 条: 风家，表解而不了了者，十二日愈。"""
        a10 = _find_article(parsed_articles, 10)
        assert a10 is not None, "第 10 条缺失"
        assert a10["content"] == "风家，表解而不了了者，十二日愈。"

    def test_article_11_starts_correctly(self, parsed_articles):
        """第 11 条: 病人身大热..."""
        a11 = _find_article(parsed_articles, 11)
        assert a11 is not None, "第 11 条缺失"
        assert a11["content"].startswith("病人身大热")

    def test_article_12_starts_correctly(self, parsed_articles):
        """第 12 条: 太阳中风..."""
        a12 = _find_article(parsed_articles, 12)
        assert a12 is not None, "第 12 条缺失"
        assert a12["content"].startswith("太阳中风")


class TestChapterAssignment:
    """章节归属测试"""

    def test_chapter_boundaries_exist(self, parsed_articles):
        """每条条文都有章节归属"""
        unassigned = [(t["article_number"], t["chapter"]) for t in parsed_articles
                      if not t.get("chapter")]
        assert len(unassigned) == 0, f"无章节归属的条号: {unassigned}"

    def test_article_1_in_taiyang(self, parsed_articles):
        """第 1 条在太阳病篇"""
        a1 = _find_article(parsed_articles, 1)
        assert a1 and "太阳" in (a1.get("chapter") or "")

    def test_article_398_in_houluan_or_yinyangyi(self, parsed_articles):
        """第 398 条在辨阴阳易差后劳复病脉证并治"""
        a398 = _find_article(parsed_articles, 398)
        assert a398 and ("阴阳易" in (a398.get("chapter") or "")
                         or "劳复" in (a398.get("chapter") or ""))


class TestDuplicateDetection:
    """重复号检测测试"""

    def test_duplicate_358_detected(self, parsed_articles):
        """条号 358 应被检测到重复（至少 2 次出现）"""
        from collections import Counter
        nums = [t["article_number"] for t in parsed_articles if t.get("article_number")]
        counts = Counter(nums)
        assert counts.get(358, 0) >= 2, f"条号 358 应出现至少 2 次，实际 {counts.get(358, 0)}"


class TestRawContent:
    """原始文本保留测试"""

    def test_raw_content_preserves_layout_marker(self, parsed_articles):
        """原始文本应保留罗马数字标记"""
        a1 = _find_article(parsed_articles, 1)
        assert a1 and "Ⅰ" in a1.get("raw_content", ""), "raw_content 应包含罗马数字 Ⅰ"

    def test_raw_content_preserves_article_number(self, parsed_articles):
        """原始文本应保留末尾条号"""
        a1 = _find_article(parsed_articles, 1)
        assert a1 and "（1）" in a1.get("raw_content", ""), "raw_content 应包含末尾条号 （1）"


class TestQualityGate:
    """质量闸门测试"""

    def test_quality_report_generates(self, parsed_articles):
        """质检报告应正确生成"""
        from app.services.import_validator import validate_import_batch

        report = validate_import_batch(parsed_articles, expected_book="《伤寒论》")
        assert report["actual_unique"] == 398
        assert report["total_parsed"] == len(parsed_articles)
        assert len(report["missing_numbers"]) == 0
        # 有重复条号，所以 passed 应为 False
        assert not report["passed"], "有重复条号（358），质检应不通过"
        assert 358 in report["duplicates"]


def _find_article(articles, number):
    """按条号查找条文"""
    for a in articles:
        if a.get("article_number") == number:
            return a
    return None
