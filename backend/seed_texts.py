"""
条文导入脚本 —— 支持《伤寒论》398条和《金匮要略》
用法：
  python seed_texts.py              # 增量导入（跳过重复）
  python seed_texts.py --clean      # 清空后全量重导
"""
import sys, os, glob, re, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, init_db
from app.models import ClassicText, ChapterMeta
from app.services.parser import DocumentParser
from app.services.text_verifier import get_verifier, SHANGHAN_CHAPTERS, JINGUI_CHAPTERS

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")


def chinese_to_int(s: str) -> int:
    """将中文数字转为整数"""
    if not s:
        return 0
    if s.isdigit():
        return int(s)
    map_cn = dict(zip("一二三四五六七八九十百千零", [1,2,3,4,5,6,7,8,9,10,100,1000,0]))
    total = 0
    unit = 1
    for ch in reversed(s):
        if ch in map_cn:
            val = map_cn[ch]
            if val >= 10:
                unit = max(unit, val)
            else:
                total += val * (unit if unit >= 10 else 1)
    return total or 1


def extract_article_number(content: str) -> int:
    """从条文内容中提取编号"""
    m = re.search(r'第\s*([一二三四五六七八九十百千零\d]+)\s*条', content)
    if m:
        return chinese_to_int(m.group(1))
    return 0


def extract_keywords(content: str) -> str:
    """从条文内容中提取关键词"""
    keywords = []
    # 方剂关键词
    formulas = [
        "桂枝汤","麻黄汤","小青龙","大青龙","真武汤","四逆汤",
        "白虎汤","承气汤","小柴胡","大柴胡","半夏泻心",
        "肾气丸","薯蓣丸","栝楼薤白","越婢汤","木防己",
        "茵陈蒿汤","栀子豉汤","理中汤","吴茱萸汤","当归四逆",
        "白头翁汤","桃花汤","桔梗汤","猪苓汤","五苓散",
    ]
    for f in formulas:
        if f in content:
            keywords.append(f)
    return ",".join(keywords[:5]) if keywords else ""


def seed(clean: bool = False):
    db = SessionLocal()
    try:
        # 初始化篇章元数据
        verifier = get_verifier()
        verifier.seed_chapter_meta(db)

        if clean:
            # 清空重导
            db.query(ClassicText).delete()
            db.commit()
            print("[clean] 已清空旧数据")

        # ───── 找到所有要处理的文档 ─────
        shanghan_files = glob.glob(os.path.join(UPLOAD_DIR, "*伤寒论*"))
        jingui_files = glob.glob(os.path.join(UPLOAD_DIR, "*金匮*"))
        
        if not shanghan_files and not jingui_files:
            all_docs = glob.glob(os.path.join(UPLOAD_DIR, "*.docx")) + glob.glob(os.path.join(UPLOAD_DIR, "*.doc"))
            if all_docs:
                print(f"[WARN] 未找到《伤寒论》或《金匮要略》文件，尝试处理 {len(all_docs)} 个文档...")
                for f in all_docs:
                    process_document(db, f)
            else:
                print("[ERR] uploads 目录下无可处理的文档！请上传 Word 文件。")
            return

        for filepath in shanghan_files:
            process_document(db, filepath)
        for filepath in jingui_files:
            process_document(db, filepath)

        # ───── 输出最终统计 ─────
        total = db.query(ClassicText).count()
        print(f"\n{'='*50}")
        print(f"[stats] 最终条文总数: {total}")
        print(f"[stats] 预期总数: 794 (伤寒398 + 金匮~396)")

        # 按书统计
        from sqlalchemy import func as sqlfunc
        books = db.query(ClassicText.source_book, sqlfunc.count(ClassicText.id)).group_by(ClassicText.source_book).all()
        for book, cnt in books:
            print(f"  {book}: {cnt}条")

        # 按篇章统计
        print("\n[dist] 篇章分布：")
        chapters = db.query(
            ClassicText.source_book, ClassicText.chapter,
            sqlfunc.count(ClassicText.id)
        ).group_by(ClassicText.source_book, ClassicText.chapter).order_by(
            ClassicText.source_book, ClassicText.chapter
        ).all()
        for book, ch, cnt in chapters:
            print(f"  {book} | {ch}: {cnt}条")

        # 无章节归属的条文
        unassigned = db.query(ClassicText).filter(
            (ClassicText.chapter == None) | (ClassicText.chapter == "")
        ).count()
        if unassigned > 0:
            print(f"\n[WARN] 无章节归属: {unassigned}条")

        # 校验数量
        verified = db.query(ClassicText).filter(ClassicText.verified == True).count()
        print(f"\n[OK] 已校验: {verified}条")

    finally:
        db.close()


def process_document(db, filepath: str):
    """处理单个文档的导入"""
    fname = os.path.basename(filepath)
    print(f"\n[file] 处理: {fname}")
    
    parser = DocumentParser(UPLOAD_DIR)
    result = parser.parse(filepath)
    content = result.get("content", "")
    print(f"   解析: {len(content)} 字符")

    extracted = parser.extract_texts_and_cases(content, fname)
    texts = extracted.get("texts", [])
    print(f"   提取: {len(texts)} 条条文")

    if not texts:
        print("   [WARN] 未提取到条文")
        return

    inserted = 0
    skipped = 0
    
    for idx, t in enumerate(texts):
        content_text = t["content"].strip()
        # 去重
        exists = db.query(ClassicText).filter(
            ClassicText.content == content_text[:200]
        ).first()
        if exists:
            skipped += 1
            continue

        article_number = extract_article_number(content_text)
        keywords = extract_keywords(content_text)
        source_book = t.get("source_book", "《伤寒论》")
        chapter = t.get("chapter")
        section = t.get("section")

        text = ClassicText(
            source_book=source_book,
            chapter=chapter,
            section=section,
            article_number=article_number,
            order_index=article_number or (idx + 1),
            content=content_text,
            keywords=keywords,
        )
        db.add(text)
        inserted += 1

    db.commit()
    print(f"   [OK] 新增: {inserted}条, 跳过(重复): {skipped}条")


if __name__ == "__main__":
    parser_arg = argparse.ArgumentParser(description="导入中医经典条文")
    parser_arg.add_argument("--clean", action="store_true", help="清空数据库后重新导入")
    args = parser_arg.parse_args()
    
    init_db()  # 确保表存在
    seed(clean=args.clean)
