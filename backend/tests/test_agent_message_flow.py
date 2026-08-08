"""训练智能体消息链路的回归测试。"""
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

from app.models import SessionMessage, TrainingSession
from app.services.agent_service import DASHSCOPE_COMPATIBLE_BASE_URL, TrainingAgent


def _create_active_session(db_session, case):
    session = TrainingSession(
        student_id="test_student",
        difficulty_level="初级",
        case_id=case.id,
        status="active",
    )
    db_session.add(session)
    db_session.commit()
    db_session.add(SessionMessage(
        session_id=session.id,
        role="agent",
        content="医生你好，我最近不太舒服。",
        message_type="question",
    ))
    db_session.commit()
    db_session.refresh(session)
    return session


class TestMessageContext:
    def test_current_input_is_sent_to_model_once(self, agent, db_session, sample_case_beginner):
        session = _create_active_session(db_session, sample_case_beginner)
        agent._call_llm = MagicMock(return_value="我这两天就是觉得关节发沉。")

        agent.process_message(db_session, session.id, "我想先问一下你哪里不舒服？")

        call = agent._call_llm.call_args
        history = call.args[1]
        current_input = call.args[2]
        assert current_input == "我想先问一下你哪里不舒服？"
        assert all(message["content"] != current_input for message in history)

    def test_ai_progress_check_runs_at_configured_interval(self, agent):
        agent.client = object()
        agent.progress_check_interval = 3
        progress = {stage: False for stage in agent.STAGES}

        two_turns = [{"role": "user", "content": "继续问诊"}] * 2
        three_turns = [{"role": "user", "content": "继续问诊"}] * 3
        four_turns = [{"role": "user", "content": "继续问诊"}] * 4

        assert agent._should_check_ai_progress(two_turns, progress) is False
        assert agent._should_check_ai_progress(three_turns, progress) is True
        assert agent._should_check_ai_progress(four_turns, progress) is False

    def test_completed_status_is_persisted(self, agent, db_session, sample_case_beginner):
        session = _create_active_session(db_session, sample_case_beginner)

        with patch.object(agent, "_call_llm", return_value="那我听你的。"), \
             patch.object(agent, "_should_end_session", return_value=True):
            _, _, status, _ = agent.process_message(db_session, session.id, "我给你开方调理。")

        db_session.refresh(session)
        assert status == "completed"
        assert session.status == "completed"
        assert session.ended_at is not None


class TestModelConfiguration:
    def test_dashscope_key_uses_openai_compatible_endpoint(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("AI_MODEL", raising=False)
        monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-test-key")
        monkeypatch.setenv("AI_TIMEOUT_SECONDS", "30")

        captured_options = {}
        fake_openai = ModuleType("openai")

        def fake_client(**options):
            captured_options.update(options)
            return object()

        fake_openai.OpenAI = fake_client
        monkeypatch.setitem(sys.modules, "openai", fake_openai)

        configured_agent = TrainingAgent()

        assert configured_agent.provider == "dashscope"
        assert configured_agent.model == "qwen-turbo"
        assert configured_agent.base_url == DASHSCOPE_COMPATIBLE_BASE_URL
        assert captured_options["api_key"] == "dashscope-test-key"
        assert captured_options["timeout"] == 30
        assert captured_options["max_retries"] == 0
