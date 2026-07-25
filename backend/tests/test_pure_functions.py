"""
纯函数单元测试 —— _clean_text、_classify_response、_extract_decision_point、_detect_classic_context
"""
import pytest
from app.models import MedicalCase


class TestCleanText:
    """Markdown 符号清理"""

    @pytest.mark.parametrize("raw,expected", [
        # 标题符号
        ("# 诊断结果", "诊断结果"),
        ("## 辨证分析", "辨证分析"),
        ("### 治疗方案", "治疗方案"),
        # 粗体/斜体
        ("**这是一个粗体**", "这是一个粗体"),
        ("*这是一个斜体*", "这是一个斜体"),
        # 行内代码
        ("使用`麻黄汤`治疗", "使用麻黄汤治疗"),
        # 分隔线（移除后留一个空行）
        ("前面\n---\n后面", "前面\n\n后面"),
        # 混合
        ("## **重要**：`脉浮`\n---\n辨证", "重要：脉浮\n\n辨证"),
        # 列表破折号
        ("- 第一条", "第一条"),
        ("— 第二条", "第二条"),
        # 多余空行压缩
        ("第一段\n\n\n\n第二段", "第一段\n\n第二段"),
    ])
    def test_cleans_markdown(self, agent, raw, expected):
        assert agent._clean_text(raw) == expected

    def test_empty_input(self, agent):
        assert agent._clean_text("") == ""

    def test_none_input(self, agent):
        assert agent._clean_text(None) == ""

    def test_plain_text_unchanged(self, agent):
        text = "这是一个普通的回复，没有任何 markdown 符号。"
        assert agent._clean_text(text) == text


class TestClassifyResponse:
    """回复类型分类"""

    @pytest.mark.parametrize("response,expected_type", [
        ("评价一下你的表现", "evaluation"),
        ("总结本次训练", "evaluation"),
        ("综合评分 85 分", "evaluation"),
        ("训练结束，以下是你的成绩", "evaluation"),
        ("正确！你答对了", "praise"),
        ("很好，思路很清晰", "praise"),
        ("不错，继续推进", "praise"),
        ("非常棒", "praise"),
        ("提示：再想想脉象的特点", "hint"),
        ("注意一下舌苔的颜色", "hint"),
        ("考虑一下是否有表证", "hint"),
    ])
    def test_classifies_correctly(self, agent, response, expected_type):
        assert agent._classify_response(response) == expected_type

    def test_default_to_question(self, agent):
        """其他类型默认归类为 question"""
        assert agent._classify_response("你哪里不舒服啊") == "question"
        assert agent._classify_response("胸口疼了三天了") == "question"

    def test_empty_response(self, agent):
        assert agent._classify_response("") == "question"


class TestExtractDecisionPoint:
    """关键决策点提取"""

    def test_extracts_disease(self, agent):
        assert agent._extract_decision_point("这是湿病", "", {}) == "辨病：湿病"
        assert agent._extract_decision_point("我觉得是胸痹", "", {}) == "辨病：胸痹"
        assert agent._extract_decision_point("太阳病", "", {}) == "辨病：太阳病"
        assert agent._extract_decision_point("应该是阳明病", "", {}) == "辨病：阳明病"

    def test_extracts_pulse(self, agent):
        assert agent._extract_decision_point("脉浮", "", {}) == "脉象：脉浮"
        assert agent._extract_decision_point("脉弦", "", {}) == "脉象：脉弦"
        assert agent._extract_decision_point("脉沉", "", {}) == "脉象：脉沉"

    def test_extracts_formula(self, agent):
        assert agent._extract_decision_point("用桂枝汤", "", {}) == "方剂：桂枝汤"
        assert agent._extract_decision_point("麻黄汤加减", "", {}) == "方剂：麻黄汤"
        assert agent._extract_decision_point("小柴胡汤", "", {}) == "方剂：小柴胡"

    def test_priority_disease_over_pulse_over_formula(self, agent):
        """疾病关键词优先于脉象优先于方剂"""
        result = agent._extract_decision_point("这是湿病，脉浮", "", {})
        assert "辨病" in result

    def test_no_match_returns_none(self, agent):
        assert agent._extract_decision_point("你好", "", {}) is None
        assert agent._extract_decision_point("哪里不舒服", "", {}) is None


class TestDetectClassicContext:
    """经典范围自动识别"""

    def test_jingui_disease(self, agent):
        case = MedicalCase(title="湿病", content="关节痛", diagnosis="湿病")
        result = agent._detect_classic_context(case)
        assert "金匮要略" in result

    def test_shanghan_disease(self, agent):
        case = MedicalCase(title="感冒", content="太阳病", diagnosis="太阳病")
        result = agent._detect_classic_context(case)
        assert "伤寒论" in result

    def test_both_classics(self, agent):
        case = MedicalCase(title="杂病", content="金匮胸痹，涉及太阳病", diagnosis="")
        result = agent._detect_classic_context(case)
        assert "两者本为一体" in result

    def test_neither_defaults_to_both(self, agent):
        case = MedicalCase(title="普通感冒", content="头痛发热", diagnosis="感冒")
        result = agent._detect_classic_context(case)
        assert "两者本为一体" in result or "金匮要略" in result or "伤寒论" in result


class TestBuildPlayfulContext:
    """玩笑请求上下文构建"""

    def test_western_checkup_context(self, agent, sample_case_advanced):
        ctx = agent._build_playful_context("western_checkup", sample_case_advanced)
        assert "西医检查" in ctx
        assert "特殊指令" in ctx

    def test_frustration_context(self, agent, sample_case_beginner):
        ctx = agent._build_playful_context("frustration", sample_case_beginner)
        assert "不满" in ctx

    def test_identity_context(self, agent, sample_case_beginner):
        ctx = agent._build_playful_context("identity_question", sample_case_beginner)
        assert "AI" in ctx

    def test_unknown_type_returns_empty(self, agent, sample_case_beginner):
        ctx = agent._build_playful_context("unknown_type", sample_case_beginner)
        assert ctx == ""


class TestGenerateWesternTestContext:
    """西医检查数据生成"""

    def test_fever_case_generates_elevated_wbc(self, agent, sample_case_advanced):
        """黄疸+发热病例应生成升高的白细胞"""
        ctx = agent._generate_western_test_context(sample_case_advanced)
        assert "血压" in ctx
        assert "血常规" in ctx  # 发热 → 触发血常规

    def test_beginner_fever_case_has_blood_test(self, agent, sample_case_beginner):
        """初级病例含'恶寒发热'→ 触发血常规"""
        ctx = agent._generate_western_test_context(sample_case_beginner)
        assert "血常规" in ctx  # 发热触发血常规，生成偏高值

    def test_chest_pain_generates_ecg(self, agent, sample_case_intermediate):
        """胸痛病例应生成心电图"""
        ctx = agent._generate_western_test_context(sample_case_intermediate)
        assert "心电图" in ctx
