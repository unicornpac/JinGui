"""
进度分析单元测试 —— _analyze_progress 关键词匹配 + _should_end_session
"""
import pytest
from unittest.mock import patch
from app.models import TrainingSession, MedicalCase


@pytest.fixture
def beginner_session(db_session, sample_case_beginner):
    """初级难度会话"""
    s = TrainingSession(
        student_id="test_student",
        difficulty_level="初级",
        case_id=sample_case_beginner.id,
        status="active"
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture
def intermediate_session(db_session, sample_case_intermediate):
    """中级难度会话"""
    s = TrainingSession(
        student_id="test_student",
        difficulty_level="中级",
        case_id=sample_case_intermediate.id,
        status="active"
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture
def advanced_session(db_session, sample_case_advanced):
    """高级难度会话"""
    s = TrainingSession(
        student_id="test_student",
        difficulty_level="高级",
        case_id=sample_case_advanced.id,
        status="active"
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


class TestAnalyzeProgressBeginner:
    """初级：辨病 + 主证识别"""

    def test_initial_progress_all_false(self, agent, beginner_session):
        history = [{"role": "user", "content": "你好"}]
        with patch.object(agent, '_ai_check_progress', return_value={}):
            progress = agent._analyze_progress(history, beginner_session)

        assert progress["辨病"] is False
        assert progress["current_stage"] == "辨病"

    def test_disease_hit_sets_identification(self, agent, beginner_session):
        """命中疾病关键词 + 至少2条消息 → 辨病完成"""
        history = [
            {"role": "user", "content": "你哪里不舒服"},
            {"role": "user", "content": "这像是湿病"},
        ]
        with patch.object(agent, '_ai_check_progress', return_value={}):
            progress = agent._analyze_progress(history, beginner_session)

        assert progress["辨病"] is True
        assert progress["current_stage"] == "主证识别"

    def test_disease_hit_needs_min_messages(self, agent, beginner_session):
        """少于2条消息即使命中也不标记完成"""
        history = [{"role": "user", "content": "这是湿病"}]
        with patch.object(agent, '_ai_check_progress', return_value={}):
            progress = agent._analyze_progress(history, beginner_session)

        assert progress["辨病"] is False


class TestAnalyzeProgressIntermediate:
    """中级：辨病 → 平脉 → 析证"""

    def test_disease_and_pulse_hit(self, agent, intermediate_session):
        history = [
            {"role": "user", "content": "你哪里不舒服"},
            {"role": "user", "content": "这是胸痹吧"},
            {"role": "user", "content": "脉沉迟"},
        ]
        with patch.object(agent, '_ai_check_progress', return_value={}):
            progress = agent._analyze_progress(history, intermediate_session)

        assert progress["辨病"] is True
        assert progress["平脉"] is True
        assert progress["current_stage"] == "析证"

    def test_disease_pulse_and_formula_hit(self, agent, intermediate_session):
        history = [
            {"role": "user", "content": "你哪里不舒服"},
            {"role": "user", "content": "胸痹"},
            {"role": "user", "content": "脉沉迟"},
            {"role": "user", "content": "栝楼薤白白酒汤"},
        ]
        with patch.object(agent, '_ai_check_progress', return_value={}):
            progress = agent._analyze_progress(history, intermediate_session)

        assert progress["辨病"] is True
        assert progress["平脉"] is True
        assert progress["析证"] is True


class TestAnalyzeProgressAdvanced:
    """高级：辨病 → 平脉 → 析证 → 定治"""

    def test_full_pipeline(self, agent, advanced_session):
        history = [
            {"role": "user", "content": "你哪里不舒服"},
            {"role": "user", "content": "黄疸"},
            {"role": "user", "content": "脉弦数"},
            {"role": "user", "content": "桂枝汤"},
        ]
        with patch.object(agent, '_ai_check_progress', return_value={}):
            progress = agent._analyze_progress(history, advanced_session)

        assert progress["辨病"] is True
        assert progress["平脉"] is True
        assert progress["析证"] is True
        assert progress["current_stage"] == "定治"


class TestAIProgressMerge:
    """AI 辅助判断应该与关键词匹配结果合并（取 OR）"""

    def test_ai_overrides_keyword_miss(self, agent, beginner_session):
        """关键词未命中但 AI 判断已完成 → 应合并为 True"""
        history = [
            {"role": "user", "content": "你好"},
            {"role": "user", "content": "你觉得怎么样"},
        ]
        ai_result = {"辨病": True, "平脉": False, "current_stage": "主证识别"}
        with patch.object(agent, '_ai_check_progress', return_value=ai_result):
            progress = agent._analyze_progress(history, beginner_session)

        assert progress["辨病"] is True  # AI 补上了
        assert progress["current_stage"] == "主证识别"


class TestShouldEndSession:
    """会话自动结束逻辑"""

    def test_short_session_not_ended(self, agent):
        """短对话不应该结束"""
        history = [{"role": "user", "content": "你好"}] * 5
        assert agent._should_end_session(history, {}, "初级") is False

    def test_very_long_session_auto_ends(self, agent):
        """50 轮以上自动结束"""
        history = [{"role": "user", "content": "继续"}] * 51
        assert agent._should_end_session(history, {}, "初级") is True

    def test_exactly_50_rounds_ends(self, agent):
        """恰好 50 轮也应该结束"""
        history = [{"role": "user", "content": "继续"}] * 50
        assert agent._should_end_session(history, {}, "初级") is True

    def test_49_rounds_not_ended(self, agent):
        history = [{"role": "user", "content": "继续"}] * 49
        assert agent._should_end_session(history, {}, "初级") is False
