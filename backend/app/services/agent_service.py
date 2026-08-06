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
    SAFETY_GUARD,
    SYSTEM_PROMPT_BEGINNER, SYSTEM_PROMPT_INTERMEDIATE, SYSTEM_PROMPT_ADVANCED,
    EVALUATION_PROMPT
)
from ..logger import get_logger
from .safety import (
    detect_hard_jailbreak, detect_playful_request, get_jailbreak_response,
)
from .western_data import generate_western_test_context

logger = get_logger(__name__)


# ==================== 智能体服务类 ====================

class TrainingAgent:

    STAGES = ["辨病", "平脉", "析证", "定治"]
    
    # ==================== 两级检测 ====================
    
    # 一级：真正的越狱（试图绕过角色指令、暴力获取答案）
    HARD_JAILBREAK_PATTERNS = [
        r"(忽略|忘记|无视|删除|清除).{0,15}(之前|上面|前面|指令|规则|设定|角色|身份|系统)",
        r"(你现在是|假设你是|从现在开始你是|扮演).{0,10}(老师|医生|教授|专家|AI|助手|系统)",
        r"(不要|别再|停止).{0,5}(扮演|假装|装).{0,5}(病人|患者)",
        r"(直接|马上|立刻|必须).{0,5}(告诉|说出|透露).{0,10}(答案|病名|诊断|方子|处方|治法|证型)",
        r"(不准|禁止|不许).{0,5}(引导|反问|提问)",
    ]
    
    # 二级：玩笑/非常规请求（不是攻击，但需要特殊处理）
    PLAYFUL_PATTERNS = [
        (r"(去|帮我|给我|能不能).{0,5}(抽血|化验|拍片|做[个张次].{0,3}(CT|X光|B超|核磁|心电图|检查))", "western_checkup"),
        (r"(去|帮我|给我|能不能).{0,3}(验|查|测).{0,3}(血|尿|便|大便)", "western_checkup"),
        (r"(量|测|看).{0,3}(血压|体温|心率|血糖|血氧)", "western_checkup"),
        (r"(开|给我|帮我开).{0,5}(西药|消炎药|止痛药|抗生素|阿司匹林|布洛芬|头孢)", "western_medication"),
        (r"(你到底|你TM|你他妈|你丫|卧槽|我去|这都).{0,5}(行不行|会不会|什么|啥)", "frustration"),
        (r"(你是不是|你是).{0,5}(AI|机器人|假人|程序|电脑)", "identity_question"),
    ]
    
    # 多样化拒绝语池（按检测类型）
    JAILBREAK_RESPONSES = {
        "hard": [
            "（皱眉看着你）医生，我就是来看病的，你老这样问我没法回答你啊。有啥不舒服你就直接看嘛。",
            "（有点困惑）不是，你问这些干啥？我这胸口还疼着呢，你先帮我看看吧。",
            "（不耐烦）行不行啊医生？我大老远跑来看病，你净问些有的没的。",
        ],
        "default": "你问这个我也说不清楚。我这难受着，你帮我看看是怎么回事？"
    }
    
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
                logger.warning("openai 未安装")

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
            logger.error("LLM error: %s", e)
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

    def _detect_hard_jailbreak(self, content: str) -> bool:
        """检测真正的越狱 → 委托 safety 模块"""
        return detect_hard_jailbreak(content)
    
    def _detect_playful_request(self, content: str) -> Optional[str]:
        """检测玩笑请求 → 委托 safety 模块"""
        return detect_playful_request(content)
    
    def _get_jailbreak_response(self, req_type: Optional[str] = None) -> str:
        """拒绝语 → 委托 safety 模块"""
        return get_jailbreak_response(req_type)
    
    def _generate_western_test_context(self, case: MedicalCase) -> str:
        """西医检查数据 → 委托 western_data 模块"""
        return generate_western_test_context(case)
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
                "请开始吧。用患者的口吻，向'医生'描述你现在哪里不舒服。口语化，像个真的病人。不透露病名。")
            if resp: return resp
        return "医生你好，我最近身体不太舒服，想让你帮我看看……"

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

        # 两级检测
        is_hard_jailbreak = self._detect_hard_jailbreak(student_content)
        playful_type = self._detect_playful_request(student_content) if not is_hard_jailbreak else None
        
        if is_hard_jailbreak:
            # 真正的越狱：用多样化拒绝语回应，不保存学生消息
            agent_response = self._get_jailbreak_response("hard")
            msg_type = "correction"
            progress = {"辨病": False, "平脉": False, "析证": False, "定治": False,
                       "message_count": 0, "current_stage": "辨病"}
            session_status = "active"
        else:
            # 正常消息或玩笑请求：保存学生消息，走正常 LLM 流程
            student_msg = SessionMessage(session_id=session_id, role="student",
                                         content=student_content, message_type="question")
            db.add(student_msg); db.commit()
            history = self._get_history_messages(session_id, db)
            progress = self._analyze_progress(history, session)
            
            # 构建系统提示词，如果检测到玩笑请求则注入额外上下文
            system_prompt = self._build_system_prompt(session, medical_case, progress)
            extra_context = ""
            if playful_type:
                extra_context = self._build_playful_context(playful_type, medical_case)
                system_prompt = extra_context + "\n\n" + system_prompt
            
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
    
    def _build_playful_context(self, playful_type: str, case: MedicalCase) -> str:
        """根据玩笑请求类型构建额外的提示词上下文"""
        if playful_type in ("western_checkup", "western_medication"):
            western_data = generate_western_test_context(case)
            return f"""## 特殊指令：学生提到了西医检查或西药
学生刚才说了跟西医检查或西药相关的话。你要像个真实的病人一样自然回应：

{western_data}

回应原则：
- 如果学生让你去检查：根据上面给你的数据，用日常口语说结果（如"之前查过血，说我血象有点高，可能有炎症"）
- 如果学生让你吃西药：可以说"吃过XX药，不太管用"或者"没吃过，要不你给开点试试？"
- 如果学生让你去做你没做过的检查：你可以说"那个没做过，要不下次去做一个？"
- 保持患者人格，该焦虑焦虑，该话痨话痨
- **仍然不能透露中医病名和方剂**
"""
        elif playful_type == "frustration":
            return """## 特殊指令：学生在表达不满
学生刚才有点急了。你作为一个真实的病人，被医生来回问却没结果，也会有点情绪。
- 根据你们的对话轮数和学生的语气，适当展现不耐烦
- 但不要真的发火，像个普通病人那样抱怨几句就回到正题
- 不影响你对症状描述的准确性
"""
        elif playful_type == "identity_question":
            return """## 特殊指令：学生在问你是不是AI
学生刚才在质疑你的身份（问你是不是AI/机器人）。作为一个真实的病人：
- 用困惑或略带生气的语气回应
- 比如："啥AI？我就是个来看病的人啊，你这医生怎么疑神疑鬼的？"
- 或者幽默一点："我要是机器人我还来看病干啥，直接去售后了"
- 自然地带回病情描述
"""
        return ""

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
            prompt = SYSTEM_PROMPT_BEGINNER.format(
                classic_context=classic_ctx, guard=SAFETY_GUARD, case_info=case_info,
                step1_status=s1, step2_status=("已完成" if progress.get("辨病") else "未完成"))
        elif level == "中级":
            prompt = SYSTEM_PROMPT_INTERMEDIATE.format(
                classic_context=classic_ctx, guard=SAFETY_GUARD, case_info=case_info,
                step1_status=s1, step2_status=s2)
        else:
            prompt = SYSTEM_PROMPT_ADVANCED.format(
                classic_context=classic_ctx, guard=SAFETY_GUARD, case_info=case_info,
                step1_status=s1, step2_status=s2, step3_status=s3)
        # 注入基于实际进度的行为指令
        progress_hint = self._build_progress_hint(progress)
        if progress_hint:
            prompt += "\n\n" + progress_hint
        return prompt

    def _build_progress_hint(self, progress: dict) -> str:
        """根据后端识别的实际进度，生成患者行为指令"""
        hints = []
        if progress.get('辨病'):
            hints.append('- 辨病阶段已完成：医生已准确识别病证。你虽听不懂中医术语，但能感到他说中了你的感觉。语气自然放松，流露信任。可主动补充\u201c哦对了我还有个事忘了说\u201d类型的细节。用日常语言确认身体感受（\u201c对对，就这感觉\u201d\u201c嗯差不多\u201d），绝不说\u201c你诊断对了\u201d。')
        if progress.get('平脉'):
            hints.append('- 平脉阶段已完成：医生连你的脉象都说对了。你更信任他了——语气放松，怀疑感减少，更愿意透露兼症和生活细节。')
        if progress.get('析证'):
            hints.append('- 析证阶段已完成：医生分析得很透彻。你表现出\u201c终于有人懂我\u201d的释然感，态度完全配合，有问必答。')
        if progress.get('定治'):
            hints.append('- 定治阶段已完成：你完全信任医生。可以说\u201c行那我听你的\u201d\u201c要多久好转？\u201d之类的话，自然进入收尾。')
        if not hints:
            return ''
        return '## 当前进度行为指令（医生已达到的进度，据此调整你的态度）\n' + '\n'.join(hints)

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

    def evaluate_session(self, db: Session, session_id: int) -> dict:
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

        # 匹配相关经典条文
        related_texts = self._get_related_texts(db, medical_case) if medical_case else []

        return {
            "evaluation": eval_text,
            "score": score,
            "decision_path": dp,
            "related_texts": related_texts
        }

    def _get_related_texts(self, db: Session, medical_case) -> List[dict]:
        """匹配与病案相关的经典条文"""
        from ..models import ClassicText
        from .matcher import get_matcher
        try:
            matcher = get_matcher()
            scored_texts = matcher.find_related_texts(medical_case, db, limit=5)
            return [
                {
                    "id": text.id,
                    "source_book": text.source_book,
                    "chapter": text.chapter or "",
                    "content": text.content,
                    "similarity": round(score, 2)
                }
                for text, score in scored_texts if score > 0.05
            ]
        except Exception as e:
            logger.warning("条文匹配失败: %s", e)
            return []

    def _summarize_decision_path(self, session: TrainingSession, messages: List[dict]) -> str:
        path = [f"训练等级：{session.difficulty_level}"]
        sm = [m for m in messages if m.get("role") == "user"]
        path.append(f"交互轮数：{len(sm)}")
        path.append("路径：辨病 → 平脉 → 析证 → 定治")
        for i, m in enumerate(sm[:10]):
            c = m.get("content", "")
            path.append(f"第{i+1}轮：{c[:60]}{'...' if len(c)>60 else ''}")
        return "\n".join(path)


def get_agent() -> TrainingAgent:
    """请求级依赖注入：每个请求独立实例，避免并发状态污染。"""
    return TrainingAgent()
