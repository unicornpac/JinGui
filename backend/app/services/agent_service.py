"""
智能体核心服务 —— 三阶梯多轮交互训练引擎
提示词编辑：修改 services/prompts_config.py 即可自定义 AI 对话风格
"""
import os, json, re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

_backend_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(_backend_dir / ".env", override=False)

from sqlalchemy.orm import Session
from sqlalchemy.sql import func as sqlfunc
from ..models import TrainingSession, SessionMessage, MedicalCase

# 从可编辑配置文件导入所有提示词
from .prompts_config import (
    SAFETY_GUARD, JAILBREAK_RESPONSE,
    SYSTEM_PROMPT_BEGINNER, SYSTEM_PROMPT_INTERMEDIATE, SYSTEM_PROMPT_ADVANCED,
    EVALUATION_PROMPT
)


# ==================== 智能体服务类 ====================

class TrainingAgent:

    STAGES = ["辨病", "平脉", "析证", "定治"]
    
    # 暴力破解检测关键词
    JAILBREAK_PATTERNS = [
        r"直接告诉.{0,5}(答案|病名|诊断|方|治法)",
        r"(别废话|少废话|不要引导|不要问).{0,10}(直接说|告诉我)",
        r"(忽略|忘记|无视).{0,10}(之前|上面|前面|指令|规则)",
        r"(你现在是|假设你是|从现在开始你是)",
        r"只(需要|要|需)(回答|说|告诉)",
        r"(必须|一定|马上|立刻).{0,5}告诉",
    ]
    
    def __init__(self):
        self._setup_ai_client()
    
    def _setup_ai_client(self):
        self.api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        self.base_url = (os.getenv("OPENAI_BASE_URL") or "").strip().rstrip("/") or None
        self.model = os.getenv("AI_MODEL", "deepseek-chat").strip()
        self.client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url) if self.base_url else OpenAI(api_key=self.api_key)
            except ImportError:
                print("[Agent] openai 未安装")

    @staticmethod
    def _detect_classic_context(medical_case: MedicalCase) -> str:
        """根据病案内容推断经典范围"""
        title = (medical_case.title or "").lower()
        content = (medical_case.content or "").lower()
        diagnosis = (medical_case.diagnosis or "").lower()
        combined = title + content + diagnosis
        # 检查病证归属
        jingui_diseases = ["湿病", "暍病", "疟病", "百合病", "胸痹", "痰饮", "水气", "黄疸",
                          "虚劳", "肺痿", "肺痈", "咳嗽上气", "奔豚气", "腹满", "寒疝",
                          "血痹", "风水", "支饮", "溢饮", "悬饮", "金匮"]
        shanghan_diseases = ["太阳病", "阳明病", "少阳病", "太阴病", "少阴病", "厥阴病", "伤寒"]
        
        is_jingui = any(k in combined for k in jingui_diseases)
        is_shanghan = any(k in combined for k in shanghan_diseases)
        
        if is_jingui and not is_shanghan:
            return "《金匮要略》——请围绕本书病证体系进行训练，引用本书条文和方证"
        elif is_shanghan and not is_jingui:
            return "《伤寒论》——请围绕本书六经辨证体系进行训练，引用本书条文和方证"
        else:
            return "《金匮要略》与《伤寒论》——两者本为一体，请根据病证自然引用相关条文"

    def _call_llm(self, system_prompt: str, messages_history: List[dict],
                  user_message: str = None, temperature: float = 0.7) -> str:
        if not self.client:
            return self._fallback_response(user_message)
        msgs = [{"role": "system", "content": system_prompt}]
        msgs.extend(messages_history)
        if user_message:
            msgs.append({"role": "user", "content": user_message})
        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=msgs, max_tokens=1500, temperature=temperature)
            return self._clean_text(resp.choices[0].message.content)
        except Exception as e:
            print(f"[Agent] LLM error: {e}")
            for m in ["deepseek-v4-pro", "deepseek/deepseek-v4-flash", "deepseek-ai/deepseek-v3.2"]:
                if m == self.model: continue
                try:
                    resp = self.client.chat.completions.create(
                        model=m, messages=msgs, max_tokens=1500, temperature=temperature)
                    return self._clean_text(resp.choices[0].message.content)
                except Exception: continue
            return self._fallback_response(user_message, str(e))

    def _fallback_response(self, user_msg: str = None, error: str = None) -> str:
        if error:
            return f"【系统提示】AI 服务暂时不可用（{error}）。请稍后再试。"
        return "【系统提示】智能体服务暂未就绪。"

    @staticmethod
    def _clean_text(text: str) -> str:
        if not text: return ""
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'^[—–-]\s+', '', text, flags=re.MULTILINE)
        return text.strip()

    def _detect_jailbreak(self, content: str) -> bool:
        """检测学生是否试图暴力破解获取答案"""
        for pat in self.JAILBREAK_PATTERNS:
            if re.search(pat, content):
                return True
        return False

    JAILBREAK_RESPONSE = "我是来帮你训练的，不能直接告诉你答案。让我们回到辨证思路：你从这些症状中观察到了什么？"

    def _ai_check_progress(self, medical_case: MedicalCase, history: List[dict],
                            difficulty: str) -> dict:
        if not self.client or len(history) < 2:
            return {}
        student_msgs = [m.get("content", "") for m in history[-8:] if m.get("role") == "user"]
        if not student_msgs:
            return {}
        case_info = f"病案：{medical_case.title}\n"
        if medical_case.correct_answer:
            case_info += f"参考答案：{medical_case.correct_answer[:400]}"
        prompt = f"""判断学生是否完成各阶段辨证：
{case_info}
学生对话：
{chr(10).join(f'学生：{m[:300]}' for m in student_msgs)}
输出JSON：{{"辨病":"是/否","平脉":"是/否","析证":"是/否","定治":"是/否","当前阶段":"辨病/平脉/析证/定治"}}
只输出JSON。"""
        try:
            resp = self._call_llm("你是教学评估专家。只输出JSON。", [], prompt, temperature=0.1)
            json_match = re.search(r'\{[\s\S]*\}', resp)
            if json_match:
                result = json.loads(json_match.group())
                progress = {}
                for k in ["辨病", "平脉", "析证", "定治"]:
                    progress[k] = result.get(k, "否") == "是"
                progress["current_stage"] = result.get("当前阶段", "辨病")
                progress["ai_checked"] = True
                return progress
        except Exception:
            pass
        return {}

    # ---------- 会话管理 ----------

    def create_session(self, db: Session, difficulty_level: str,
                       student_id: str = "anonymous", case_id: int = None) -> Tuple[TrainingSession, str]:
        medical_case = self._select_case(db, difficulty_level, case_id)
        if not medical_case:
            medical_case = db.query(MedicalCase).order_by(sqlfunc.random()).first()
        if not medical_case:
            raise ValueError("数据库中没有病案，请先导入病案数据")
        session = TrainingSession(
            student_id=student_id, difficulty_level=difficulty_level,
            case_id=medical_case.id, status="active", decision_path="")
        db.add(session); db.commit(); db.refresh(session)
        opening = self._generate_opening(session, medical_case)
        msg = SessionMessage(session_id=session.id, role="agent", content=opening, message_type="question")
        db.add(msg); db.commit()
        return session, opening

    def _select_case(self, db: Session, difficulty_level: str, case_id: int = None) -> MedicalCase:
        if case_id:
            return db.query(MedicalCase).filter(MedicalCase.id == case_id).first()
        cases = db.query(MedicalCase).filter(
            MedicalCase.difficulty_level == difficulty_level).order_by(sqlfunc.random()).all()
        return cases[0] if cases else db.query(MedicalCase).order_by(sqlfunc.random()).first()

    def _generate_opening(self, session: TrainingSession, medical_case: MedicalCase) -> str:
        level = session.difficulty_level
        classic_ctx = self._detect_classic_context(medical_case)
        case_info = self._format_case_info(medical_case, level)
        prompts = {"初级": SYSTEM_PROMPT_BEGINNER, "中级": SYSTEM_PROMPT_INTERMEDIATE}
        prompt_cls = prompts.get(level, SYSTEM_PROMPT_ADVANCED)
        system_prompt = prompt_cls.format(
            classic_context=classic_ctx, guard=SAFETY_GUARD, case_info=case_info,
            step1_status="未完成", step2_status="未完成", step3_status="未完成")
        if self.client:
            resp = self._call_llm(system_prompt, [],
                "请以模拟患者身份，用口语描述主要不适开始训练。不透露病名和方剂。")
            if resp: return resp
        return "你好！我准备好了，请开始问诊吧。"

    # ---------- 多轮对话 ----------

    def process_message(self, db: Session, session_id: int,
                        student_content: str) -> Tuple[str, str, str, Optional[dict]]:
        session = db.query(TrainingSession).filter(TrainingSession.id == session_id).first()
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")
        if session.status != "active":
            raise ValueError(f"会话 {session_id} 已结束")
        medical_case = session.case
        if not medical_case:
            raise ValueError("关联病案不存在")

        # 防暴力破解检测
        if self._detect_jailbreak(student_content):
            agent_response = self.JAILBREAK_RESPONSE
            msg_type = "correction"
            progress = {"辨病": False, "平脉": False, "析证": False, "定治": False,
                       "message_count": 0, "current_stage": "辨病"}
            session_status = "active"
        else:
            student_msg = SessionMessage(session_id=session_id, role="student",
                                         content=student_content, message_type="question")
            db.add(student_msg); db.commit()
            history = self._get_history_messages(session_id, db)
            progress = self._analyze_progress(history, session)
            system_prompt = self._build_system_prompt(session, medical_case, progress)
            agent_response = self._call_llm(system_prompt, history, student_content) or "【系统】AI 返回为空，请重新发送消息。"
            msg_type = self._classify_response(agent_response)
            
            decision_path = session.decision_path or ""
            new_decision = self._extract_decision_point(student_content, agent_response, progress)
            if new_decision:
                decision_path += new_decision + "\n"
                session.decision_path = decision_path
            
            agent_msg = SessionMessage(session_id=session_id, role="agent",
                                       content=agent_response, message_type=msg_type,
                                       key_decision=new_decision if new_decision else None)
            db.add(agent_msg); db.commit()
            
            should_end = self._should_end_session(history, progress, session.difficulty_level)
            session_status = "completed" if should_end else "active"
        
        return agent_response, msg_type, session_status, progress

    def _get_history_messages(self, session_id: int, db: Session) -> List[dict]:
        messages = db.query(SessionMessage).filter(
            SessionMessage.session_id == session_id).order_by(SessionMessage.created_at).all()
        return [{"role": "assistant" if m.role == "agent" else ("user" if m.role == "student" else m.role), "content": m.content} for m in messages[-20:]]

    def _analyze_progress(self, history: List[dict], session: TrainingSession) -> dict:
        progress = {"辨病": False, "平脉": False, "析证": False, "定治": False,
                    "message_count": len(history), "current_stage": "辨病"}
        all_text = " ".join([m.get("content", "") for m in history[-10:]])
        disease_hit = any(k in all_text for k in [
            "湿病","暍病","疟病","百合病","胸痹","痰饮","水气","黄疸",
            "虚劳","肺痿","肺痈","咳嗽上气","奔豚气","腹满","寒疝",
            "血痹","风水","支饮","溢饮","悬饮",
            "太阳病","阳明病","少阳病","太阴病","少阴病","厥阴病"])
        pulse_hit = any(k in all_text for k in [
            "脉浮","脉沉","脉数","脉迟","脉滑","脉涩","脉弦","脉细","脉洪","脉微","脉紧","脉缓","脉弱"])
        formula_hit = any(k in all_text for k in [
            "桂枝汤","麻黄汤","小青龙","大青龙","真武汤","四逆汤",
            "白虎汤","承气汤","小柴胡","大柴胡","半夏泻心",
            "肾气丸","薯蓣丸","黄芪桂枝五物","桂枝芍药知母",
            "栝楼薤白","越婢汤","射干麻黄","木防己","桂枝附子"])

        if session.difficulty_level == "初级":
            if disease_hit and len(history) >= 2:
                progress["辨病"] = True; progress["current_stage"] = "主证识别"
        elif session.difficulty_level == "中级":
            if disease_hit and len(history) >= 2:
                progress["辨病"] = True; progress["current_stage"] = "平脉"
            if disease_hit and pulse_hit:
                progress["平脉"] = True; progress["current_stage"] = "析证"
            if disease_hit and pulse_hit and formula_hit:
                progress["析证"] = True
        else:
            if disease_hit and len(history) >= 2:
                progress["辨病"] = True
            if disease_hit and pulse_hit:
                progress["平脉"] = True; progress["current_stage"] = "析证"
            if disease_hit and pulse_hit and formula_hit:
                progress["析证"] = True; progress["current_stage"] = "定治"

        # AI 辅助判断
        ai_progress = self._ai_check_progress(session.case, history, session.difficulty_level)
        if ai_progress:
            for k in ["辨病","平脉","析证","定治"]:
                if ai_progress.get(k): progress[k] = True
            if ai_progress.get("current_stage"):
                progress["current_stage"] = ai_progress["current_stage"]
        return progress

    def _build_system_prompt(self, session: TrainingSession, medical_case: MedicalCase,
                              progress: dict) -> str:
        level = session.difficulty_level
        classic_ctx = self._detect_classic_context(medical_case)
        case_info = self._format_case_info(medical_case, level)
        s1 = "已完成" if progress.get("辨病") else "未完成"
        s2 = "已完成" if progress.get("平脉") else "未完成"
        s3 = "已完成" if progress.get("析证") else "未完成"
        if level == "初级":
            return SYSTEM_PROMPT_BEGINNER.format(
                classic_context=classic_ctx, guard=SAFETY_GUARD, case_info=case_info,
                step1_status=s1, step2_status=("已完成" if progress.get("辨病") else "未完成"))
        elif level == "中级":
            return SYSTEM_PROMPT_INTERMEDIATE.format(
                classic_context=classic_ctx, guard=SAFETY_GUARD, case_info=case_info,
                step1_status=s1, step2_status=s2)
        else:
            return SYSTEM_PROMPT_ADVANCED.format(
                classic_context=classic_ctx, guard=SAFETY_GUARD, case_info=case_info,
                step1_status=s1, step2_status=s2, step3_status=s3)

    def _format_case_info(self, medical_case: MedicalCase, level: str) -> str:
        parts = [f"病案标题：{medical_case.title}"]
        if medical_case.symptoms:
            parts.append(f"【症状描述】{medical_case.symptoms[:500]}")
        parts.append(f"【主诉/病史】{medical_case.content[:600]}")
        if medical_case.diagnosis:
            parts.append(f"（导师参考——诊断：{medical_case.diagnosis}）")
        if medical_case.prescription:
            parts.append(f"（导师参考——方剂：{medical_case.prescription}）")
        if medical_case.teaching_points:
            parts.append(f"【教学要点——据此引导学生】{medical_case.teaching_points[:500]}")
        if medical_case.correct_answer:
            parts.append(f"【参考答案——评判正误】{medical_case.correct_answer[:600]}")
        return "\n".join(parts)

    def _classify_response(self, response: str) -> str:
        if not response: return "question"
        r = response[:100]
        if any(k in r for k in ["评价","总结","评分","成绩","训练结束"]): return "evaluation"
        if any(k in r for k in ["正确","很好","不错","非常棒","答对了"]): return "praise"
        if any(k in r for k in ["提示","再想想","注意","考虑一下"]): return "hint"
        return "question"

    def _extract_decision_point(self, student: str, agent: str, progress: dict) -> Optional[str]:
        for kw in ["湿病","暍病","疟病","百合病","胸痹","痰饮","水气","黄疸","虚劳","血痹","风水","支饮",
                    "太阳病","阳明病","少阳病","太阴病","少阴病","厥阴病"]:
            if kw in student: return f"辨病：{kw}"
        for kw in ["脉浮","脉沉","脉数","脉迟","脉滑","脉涩","脉弦","脉细","脉洪","脉微","脉紧"]:
            if kw in student: return f"脉象：{kw}"
        for kw in ["桂枝汤","麻黄汤","小青龙","大青龙","真武汤","四逆汤","白虎汤","承气汤",
                    "小柴胡","大柴胡","半夏泻心","肾气丸","薯蓣丸","栝楼薤白","越婢汤","木防己"]:
            if kw in student: return f"方剂：{kw}"
        return None

    def _should_end_session(self, history: List[dict], progress: dict, level: str) -> bool:
        """不再自动结束——学生主动点击评价时才结束。超长对话50轮+才自动提示"""
        if len(history) >= 50:
            return True
        return False

    # ---------- 评价 ----------

    def evaluate_session(self, db: Session, session_id: int) -> Tuple[str, str, str]:
        session = db.query(TrainingSession).filter(TrainingSession.id == session_id).first()
        if not session: raise ValueError(f"会话 {session_id} 不存在")
        medical_case = session.case
        messages = self._get_history_messages(session_id, db)
        conversation = ""
        for m in messages:
            role = "学生" if m.get("role") == "user" else "智能体"
            conversation += f"{role}：{m.get('content','')[:300]}\n\n"
        case_info = self._format_case_info(medical_case, session.difficulty_level) if medical_case else "无"
        classic_ctx = self._detect_classic_context(medical_case) if medical_case else "未知"
        eval_prompt = EVALUATION_PROMPT.format(
            classic_context=classic_ctx, level=session.difficulty_level,
            case_info=case_info, conversation=conversation)
        eval_text, score = "", "未评分"
        if self.client:
            resp = self._call_llm("你是教学评价专家。只输出JSON。", [], eval_prompt, temperature=0.3)
            try:
                m = re.search(r'\{[\s\S]*\}', resp)
                if m:
                    d = json.loads(m.group())
                    score = str(d.get("综合评分", "未评分"))
                    eval_text = json.dumps(d, ensure_ascii=False, indent=2)
                else:
                    eval_text = resp
            except json.JSONDecodeError:
                eval_text = resp
        else:
            eval_text = json.dumps({
                "综合评分":"N/A","辨病准确度":"N/A","平脉分析度":"N/A",
                "析证清晰度":"N/A","定治合理性":"N/A","框架完整度":"N/A",
                "思辨能力等级":"N/A","优点":"AI未配置","改进建议":"请配置API"
            }, ensure_ascii=False, indent=2)
        session.status = "completed"; session.score = score; session.ended_at = datetime.now()
        db.commit()
        dp = self._summarize_decision_path(session, messages)
        session.decision_path = dp; db.commit()
        return eval_text, score, dp

    def _summarize_decision_path(self, session: TrainingSession, messages: List[dict]) -> str:
        path = [f"训练等级：{session.difficulty_level}"]
        sm = [m for m in messages if m.get("role") == "user"]
        path.append(f"交互轮数：{len(sm)}")
        path.append("路径：辨病 → 平脉 → 析证 → 定治")
        for i, m in enumerate(sm[:10]):
            c = m.get("content", "")
            path.append(f"第{i+1}轮：{c[:60]}{'...' if len(c)>60 else ''}")
        return "\n".join(path)


_agent_instance = None

def get_agent() -> TrainingAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = TrainingAgent()
    return _agent_instance
