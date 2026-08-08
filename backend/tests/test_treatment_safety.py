"""方剂回应与训练安全复盘的回归测试。"""
import json
from unittest.mock import MagicMock, patch

from app.models import SessionMessage, TrainingSession
from app.services.treatment_safety import (
    assess_treatment_message,
    assess_treatment_safety,
    build_patient_treatment_context,
)


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
    return session


class TestTreatmentAssessment:
    def test_expected_formula_is_recognized_without_patient_judgement(self):
        result = assess_treatment_safety(
            [{"role": "user", "content": "我拟用麻黄加术汤。"}],
            "麻黄加术汤",
        )

        assert result["level"] == "pass"
        assert result["matches_expected"] is True

    def test_other_formula_requires_case_review(self):
        result = assess_treatment_safety(
            [{"role": "user", "content": "我给你开桂枝汤。"}],
            "麻黄加术汤",
        )

        assert result["level"] == "warning"
        assert "方证对应" in result["title"]

    def test_high_risk_numeric_dose_is_critical_without_claiming_a_real_outcome(self):
        result = assess_treatment_safety(
            [{"role": "user", "content": "我给你开朱砂50g。"}],
            "麻黄加术汤",
        )

        assert result["level"] == "critical"
        assert "死亡" not in result["summary"]
        assert "不得执行" in result["summary"]

    def test_patient_context_accepts_normal_prescription(self):
        assessment = assess_treatment_message("我给你开桂枝汤。", "麻黄加术汤")
        context = build_patient_treatment_context(assessment)

        assert "不要仅因听到方剂名就说“啥意思”" in context

    def test_patient_context_requests_recheck_for_critical_plan(self):
        assessment = assess_treatment_message("我给你开朱砂50g。", "麻黄加术汤")
        context = build_patient_treatment_context(assessment)

        assert "不要直接答应服用" in context


class TestTreatmentIntegration:
    def test_patient_prompt_excludes_hidden_answer_and_prescription(
        self, agent, sample_case_beginner
    ):
        session = TrainingSession(difficulty_level="初级")
        prompt = agent._build_system_prompt(
            session,
            sample_case_beginner,
            {"辨病": False, "平脉": False, "析证": False, "定治": False},
        )

        assert sample_case_beginner.title not in prompt
        assert sample_case_beginner.diagnosis not in prompt
        assert sample_case_beginner.prescription not in prompt
        assert sample_case_beginner.correct_answer not in prompt

    def test_formula_message_injects_natural_patient_response_context(
        self, agent, db_session, sample_case_beginner
    ):
        session = _create_active_session(db_session, sample_case_beginner)
        agent.client = None
        agent._call_llm = MagicMock(return_value="好，那就按您说的办。")

        agent.process_message(db_session, session.id, "我给你开麻黄加术汤。")

        system_prompt = agent._call_llm.call_args.args[0]
        assert "当前医嘱回应" in system_prompt
        assert "不要仅因听到方剂名就说“啥意思”" in system_prompt

    def test_critical_treatment_forces_training_safety_failure(
        self, agent, db_session, sample_case_beginner
    ):
        session = _create_active_session(db_session, sample_case_beginner)
        db_session.add(SessionMessage(
            session_id=session.id,
            role="student",
            content="我给你开朱砂50g。",
            message_type="question",
        ))
        db_session.commit()
        agent.client = object()

        evaluation = {
            "综合评分": 88,
            "辨病准确度": 80,
            "平脉分析度": "N/A",
            "析证清晰度": 80,
            "定治合理性": 80,
            "框架完整度": 80,
            "思辨能力等级": "B",
            "优点": "有尝试",
            "改进建议": "继续复盘",
        }
        with patch.object(agent, "_call_llm", return_value=json.dumps(evaluation)), \
             patch.object(agent, "_get_related_texts", return_value=[]):
            result = agent.evaluate_session(db_session, session.id)

        assert result["score"] == "0"
        assert result["safety_feedback"]["level"] == "critical"
        assert json.loads(result["evaluation"])["综合评分"] == 0
