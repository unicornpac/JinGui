"""
伤寒论398条条文导入脚本
从上传的 Word 文档中解析并导入经典条文库
用法：python3 seed_texts.py
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import ClassicText
from app.services.parser import DocumentParser


def seed():
    # 找到上传的伤寒论文档
    upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
    candidates = glob.glob(os.path.join(upload_dir, "*伤寒论*"))
    if not candidates:
        print("未找到伤寒论文档，尝试全部 Word 文件...")
        candidates = glob.glob(os.path.join(upload_dir, "*.docx"))

    if not candidates:
        print("❌ uploads 目录下无 Word 文档！")
        return

    filepath = max(candidates, key=os.path.getsize)  # 取最大的
    print(f"📄 使用文件: {os.path.basename(filepath)} ({os.path.getsize(filepath)} bytes)")

    # 解析
    parser = DocumentParser(upload_dir)
    result = parser.parse(filepath)
    content = result.get("content", "")
    print(f"📝 解析完成: {len(content)} 字符")

    # 提取条文
    extracted = parser.extract_texts_and_cases(content, os.path.basename(filepath))
    texts = extracted.get("texts", [])
    print(f"📋 提取到 {len(texts)} 条条文")

    if not texts:
        print("❌ 未提取到条文，检查文档格式")
        return

    # 写入数据库
    db = SessionLocal()
    try:
        existing_count = db.query(ClassicText).count()
        print(f"📊 当前条文数: {existing_count}")

        inserted = 0
        skipped = 0
        for t in texts:
            content_text = t["content"].strip()
            # 跳过重复
            exists = db.query(ClassicText).filter(
                ClassicText.content == content_text[:200]
            ).first()
            if exists:
                skipped += 1
                continue

            # 提取条文编号作为关键词
            import re
            num_match = re.search(r'第\s*(\d+|[一二三四五六七八九十百千零]+)\s*条', content_text)
            keywords = f"第{num_match.group(1)}条" if num_match else ""

            text = ClassicText(
                source_book=t.get("source_book", "《伤寒论》"),
                chapter=t.get("chapter"),
                content=content_text,
                keywords=keywords
            )
            db.add(text)
            inserted += 1

        db.commit()
        print(f"\n✅ 导入完成！新增 {inserted} 条，跳过 {skipped} 条（已存在）")
        print(f"📊 当前条文总数: {db.query(ClassicText).count()}")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
