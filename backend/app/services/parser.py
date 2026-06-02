"""
文档解析服务
支持PDF、Word、TXT、Excel等格式的解析
自动识别中医经典条文格式并归类到条文库
"""
import os
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

try:
    import pandas as pd
except ImportError:
    pd = None

# 中医经典来源与章节关键词映射
SOURCE_BOOK_KEYWORDS = {
    "《伤寒论》": ["伤寒论", "伤寒"],
    "《金匮要略》": ["金匮", "金匮要略"],
    "《温病条辨》": ["温病", "温病条辨"],
    "《黄帝内经》": ["内经", "素问", "灵枢"],
}


class DocumentParser:
    """文档解析器"""
    
    def __init__(self, upload_dir: str = None):
        """
        初始化解析器
        
        Args:
            upload_dir: 上传文件存储目录
        """
        self.upload_dir = upload_dir or "uploads"
        os.makedirs(self.upload_dir, exist_ok=True)
    
    def parse(self, file_path: str, file_type: str = None) -> Dict[str, any]:
        """
        解析文档
        
        Args:
            file_path: 文件路径
            file_type: 文件类型（可选，会自动检测）
        
        Returns:
            包含解析结果的字典
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 自动检测文件类型
        if not file_type:
            file_type = self._detect_file_type(file_path)
        
        # 根据文件类型选择解析方法
        if file_type == "application/pdf" or file_path.lower().endswith('.pdf'):
            return self._parse_pdf(file_path)
        elif file_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                          "application/msword"] or file_path.lower().endswith(('.docx', '.doc')):
            return self._parse_word(file_path)
        elif file_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                          "application/vnd.ms-excel"] or file_path.lower().endswith(('.xlsx', '.xls')):
            return self._parse_excel(file_path)
        elif file_type == "text/plain" or file_path.lower().endswith('.txt'):
            return self._parse_txt(file_path)
        else:
            # 默认按文本文件处理
            return self._parse_txt(file_path)
    
    def _detect_file_type(self, file_path: str) -> str:
        """根据文件扩展名检测文件类型"""
        ext = Path(file_path).suffix.lower()
        type_map = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.txt': 'text/plain'
        }
        return type_map.get(ext, 'text/plain')
    
    def _parse_pdf(self, file_path: str) -> Dict[str, any]:
        """解析PDF文件"""
        if pdfplumber is None:
            raise ImportError("pdfplumber未安装，请运行: pip install pdfplumber")
        
        text_content = ""
        pages_count = 0
        try:
            with pdfplumber.open(file_path) as pdf:
                pages_count = len(pdf.pages)
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_content += page_text + "\n"
        except Exception as e:
            raise Exception(f"PDF解析失败: {str(e)}")
        
        return {
            "content": text_content.strip(),
            "pages": pages_count,
            "file_type": "pdf"
        }
    
    def _parse_word(self, file_path: str) -> Dict[str, any]:
        """解析Word文件"""
        if DocxDocument is None:
            raise ImportError("python-docx未安装，请运行: pip install python-docx")
        
        try:
            doc = DocxDocument(file_path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            text_content = "\n".join(paragraphs).strip()
        except Exception as e:
            raise Exception(f"Word解析失败: {str(e)}")
        
        return {
            "content": text_content,
            "paragraphs": len(paragraphs),
            "file_type": "word"
        }
    
    def _parse_excel(self, file_path: str) -> Dict[str, any]:
        """解析Excel文件，优先识别条文结构（编号、内容、来源等列）"""
        if pd is None:
            raise ImportError("pandas未安装，请运行: pip install pandas openpyxl")
        
        all_text = []
        sheets_count = 0
        try:
            excel_file = pd.ExcelFile(file_path)
            sheets_count = len(excel_file.sheet_names)
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
                df = df.dropna(how='all').fillna('')
                # 尝试识别条文结构：首行可能是列名
                first_row = [str(v).lower() for v in df.iloc[0]] if len(df) > 0 else []
                content_col = None
                for i, c in enumerate(first_row):
                    if any(k in c for k in ['内容', '条文', '正文', 'text', 'content']):
                        content_col = i
                        break
                if content_col is None and len(df.columns) >= 2:
                    content_col = 1
                elif content_col is None:
                    content_col = 0
                # 若首行像列名，跳过
                start_row = 1 if any(k in ' '.join(first_row) for k in ['编号', '条', '内容', '来源']) else 0
                
                rows = []
                for idx in range(start_row, len(df)):
                    row = df.iloc[idx]
                    vals = [str(v).strip() for v in row if str(v).strip()]
                    if not vals:
                        continue
                    cell = vals[content_col] if content_col < len(vals) else (vals[-1] if vals else "")
                    if cell and len(cell) > 15:
                        rows.append(cell)
                
                sheet_text = f"\n=== 工作表: {sheet_name} ===\n" + "\n\n".join(rows)
                all_text.append(sheet_text)
            
            text_content = "\n\n".join(all_text).strip()
        except Exception as e:
            raise Exception(f"Excel解析失败: {str(e)}")
        
        return {
            "content": text_content,
            "sheets": sheets_count,
            "file_type": "excel"
        }
    
    def _parse_txt(self, file_path: str) -> Dict[str, any]:
        """解析TXT文件"""
        try:
            # 尝试多种编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            text_content = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        text_content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if text_content is None:
                raise Exception("无法使用常见编码读取文件")
        except Exception as e:
            raise Exception(f"TXT解析失败: {str(e)}")
        
        return {
            "content": text_content,
            "file_type": "txt"
        }
    
    def _detect_source_and_chapter(self, content: str, filename: str = "") -> Tuple[str, Optional[str]]:
        """从内容或文件名推断来源经典和章节"""
        combined = (content[:2000] + " " + filename).lower()
        source_book = "未知经典"
        chapter = None
        
        for book, keywords in SOURCE_BOOK_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                source_book = book
                break
        
        # 章节识别（伤寒论六经辨证等）
        chapter_patterns = [
            (r'辨(太阳|阳明|少阳|太阴|少阴|厥阴)病脉证并治[（(]?[上下中]?[)）]?', r'辨\1病脉证并治'),
            (r'辨霍乱病脉证并治', '辨霍乱病脉证并治'),
            (r'辨阴阳易差后劳复病脉证并治', '辨阴阳易差后劳复病脉证并治'),
        ]
        for pat, repl in chapter_patterns:
            m = re.search(pat, content[:1500])
            if m:
                chapter = m.group(0).strip()
                break
        
        return source_book, chapter

    def _normalize_content(self, content: str) -> str:
        """标准化文本：统一换行、去除多余空白"""
        if not content:
            return ""
        s = content.replace("\r\n", "\n").replace("\r", "\n")
        s = re.sub(r'[ \t]+', ' ', s)  # 制表符、多空格变单空格
        s = re.sub(r'\n[ \t]+', '\n', s)  # 行首空白
        s = re.sub(r'[ \t]+\n', '\n', s)  # 行尾空白
        return s.strip()

    def _find_tiao_starts(self, content: str, prefer_di_tiao: bool = True) -> List[Tuple[int, str]]:
        """
        找出所有条文起始位置
        prefer_di_tiao: 若存在「第X条」则只用该格式，避免与条文内容中的「1. 桂枝」等混淆
        """
        starts = []
        # 格式1：第X条、第 X 条、第一条（支持空格）
        for m in re.finditer(r'第\s*([一二三四五六七八九十百千零\d]+)\s*条', content):
            starts.append((m.start(), m.group(0)))
        # 格式2：仅当无「第X条」时，用行首 1. 2. 3.（排除 1.2.3 这类非条文编号）
        if not starts or not prefer_di_tiao:
            for m in re.finditer(r'(?:^|\n\n)\s*(\d{1,3})\s*[\.\、．。]\s*(?=\n|[^\d\s])', content, re.MULTILINE):
                num = int(m.group(1))
                if 1 <= num <= 500:
                    starts.append((m.start(), m.group(0)))
        # 去重、按位置排序
        seen_pos = set()
        unique = []
        for pos, tag in sorted(starts, key=lambda x: x[0]):
            if pos not in seen_pos:
                seen_pos.add(pos)
                unique.append((pos, tag))
        return unique

    def _split_by_tiaohao(self, content: str) -> List[str]:
        """
        按「第X条」或数字编号精确分割
        支持：第1条、第 1 条、第一条、1. 2. 3.、1、2、3 等格式
        """
        content = self._normalize_content(content)
        # 优先用「第X条」，若数量>=2则只用该格式
        di_tiao_matches = list(re.finditer(r'第\s*([一二三四五六七八九十百千零\d]+)\s*条', content))
        prefer_di_tiao = len(di_tiao_matches) >= 2
        starts = self._find_tiao_starts(content, prefer_di_tiao=prefer_di_tiao)
        if not starts:
            return []

        result = []
        for i, (pos, _) in enumerate(starts):
            end = starts[i + 1][0] if i + 1 < len(starts) else len(content)
            t = content[pos:end].strip()
            # 排除章节标题（整段仅为辨XX病脉证并治）
            if re.match(r'^辨[^\n]{0,40}病脉证并治', t) and '第' not in t[:25]:
                continue
            # 去掉末尾的章节标题行（避免误计入条文内容）
            t = re.sub(r'\n辨[^\n]{0,35}病脉证并治[^\n]*$', '', t)
            t = re.sub(r'\n{3,}', '\n\n', t).strip()
            # 若单条内又含「第X条」，说明被合并了，按内部标记再切分
            inner = re.finditer(r'第\s*([一二三四五六七八九十百千零\d]+)\s*条', t)
            inner_list = list(inner)
            if len(inner_list) >= 2:
                for j, im in enumerate(inner_list):
                    start_inner = im.start()
                    end_inner = inner_list[j + 1].start() if j + 1 < len(inner_list) else len(t)
                    sub = t[start_inner:end_inner].strip()
                    sub = re.sub(r'\n辨[^\n]{0,35}病脉证并治[^\n]*$', '', sub).strip()
                    if 10 < len(sub) < 2500:
                        result.append(sub)
            elif 10 < len(t) < 2500:
                result.append(t)
        return result

    def extract_texts_and_cases(
        self, content: str, filename: str = ""
    ) -> Dict[str, any]:
        """
        从解析的文本中提取条文和病案，并识别来源经典、章节
        优先按「第X条」精确分割，避免伤寒论398条断句错误与混淆
        """
        source_book, chapter = self._detect_source_and_chapter(content, filename)
        texts_raw = []
        cases_raw = []
        seen_texts = set()

        # ========== 策略1：按「第X条」精确分割（伤寒论398条等）==========
        tiao_items = self._split_by_tiaohao(content)
        if tiao_items:
            for t in tiao_items:
                t_clean = t[:2000].strip()
                if t_clean and t_clean not in seen_texts and 15 < len(t_clean) < 2000:
                    seen_texts.add(t_clean)
                    texts_raw.append({
                        "content": t_clean,
                        "source_book": source_book,
                        "chapter": chapter
                    })
            # 若已按第X条成功分割，且数量较多，视为纯条文文档，不再提取病案
            if len(texts_raw) >= 5:
                return {"texts": texts_raw, "cases": cases_raw}

        # ========== 策略2：其他条文格式（第X条单条匹配、数字编号等）==========
        if not texts_raw:
            patterns = [
                (r'第[一二三四五六七八九十百千\d]+条[：:\.\s]*([^\n]+(?:\n(?![第\d一二三四五六七八九十百千]+条)[^\n]*)*)', 1),
                (r'^\s*(\d{1,3})[\.\、\s]+([^\n]+(?:\n(?!^\s*\d{1,3}[\.\、])[^\n]*)*)', 2),
            ]
            for pattern, grp in patterns:
                for m in re.finditer(pattern, content, re.MULTILINE):
                    t = (m.group(grp) if m.lastindex >= grp else m.group(0)).strip()
                    if 15 < len(t) < 1500 and t not in seen_texts:
                        seen_texts.add(t)
                        texts_raw.append({"content": t[:2000], "source_book": source_book, "chapter": chapter})

        # ========== 策略3：六经病开头（仅当第X条未匹配到时）==========
        if not tiao_items:
            for sep in ['太阳病', '阳明病', '少阳病', '太阴病', '少阴病', '厥阴病']:
                parts = content.split(sep)
                for p in parts[1:]:
                    rest = p.strip()
                    for next_s in ['太阳病', '阳明病', '少阳病', '太阴病', '少阴病', '厥阴病', '伤寒']:
                        if next_s in rest:
                            rest = rest[:rest.find(next_s)].strip()
                    t = (sep + rest).strip() if rest else ""
                    if 25 < len(t) < 800 and t not in seen_texts:
                        seen_texts.add(t)
                        texts_raw.append({"content": t[:2000], "source_book": source_book, "chapter": chapter})

        # ========== 病案提取（仅在非纯条文文档时）==========
        case_keywords = ['患者', '主诉', '现病史', '方药', '处方', '诊断', '症见']
        has_case_hint = any(k in content for k in case_keywords)
        if has_case_hint or len(texts_raw) < 10:
            case_patterns = [
                r'病案[：:\s]*\n([^\n]+(?:\n(?!病案|案例|第\d+条)[^\n]*){2,})',
                r'案例[：:\s]*\n([^\n]+(?:\n(?!病案|案例|第\d+条)[^\n]*){2,})',
                r'(患者[^\n]+(?:\n[^\n]+){4,}?)(?=\n\n患者|\n\n病案|第\d+条|$)',
            ]
            for pattern in case_patterns:
                for m in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                    c = (m.group(1) if m.lastindex >= 1 else m.group(0)).strip()
                    if len(c) > 80 and not any(t["content"] == c[:500] for t in cases_raw):
                        title = c.split("\n")[0][:50] if c else "病案"
                        cases_raw.append({"content": c[:2000], "title": title})

        # ========== 兜底：按段落分割 ==========
        if not texts_raw and not cases_raw:
            paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if len(p.strip()) > 30]
            for para in paragraphs:
                if any(k in para for k in ['太阳病', '阳明病', '伤寒', '桂枝', '麻黄']) and len(para) < 500:
                    if para not in seen_texts:
                        seen_texts.add(para)
                        texts_raw.append({"content": para[:2000], "source_book": source_book, "chapter": chapter})
                elif any(k in para for k in case_keywords) and len(para) > 60:
                    cases_raw.append({"content": para[:2000], "title": para.split("\n")[0][:50] or "病案"})

        return {"texts": texts_raw, "cases": cases_raw}
