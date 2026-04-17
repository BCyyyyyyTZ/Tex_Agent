import fitz
from datetime import datetime

def add_highlight_with_comment(input_path, output_path, page_idx, text_to_highlight, comment_text, author="唐骏涛"):
    """
    高亮 PDF 中的文本并添加注释
    :param input_path: 原始 PDF 路径
    :param output_path: 输出 PDF 路径
    :param page_idx: 页码（从 0 开始）
    :param text_to_highlight: 要高亮的文本内容
    :param comment_text: 注释内容
    :param author: 标注者名称
    """
    # 打开 PDF
    doc = fitz.open(input_path)
    
    if not (0 <= page_idx < len(doc)):
        raise ValueError(f"页码无效，该 PDF 共有 {len(doc)} 页（索引 0~{len(doc)-1}）")
    
    page = doc[page_idx]
    
    # 查找要高亮的文本
    text_instances = page.search_for(text_to_highlight)
    
    if not text_instances:
        print(f"⚠️ 未找到文本: '{text_to_highlight}'")
        doc.close()
        return False
    
    # 格式化时间
    now = datetime.now()
    creation_date_str = f"D:{now.strftime('%Y%m%d%H%M%S')}"
    
    # 为每个找到的文本实例添加高亮和注释
    for inst in text_instances:
        # 添加高亮
        highlight = page.add_highlight_annot(inst)
        highlight.set_info(
            title=author,
            content=comment_text,
            creationDate=creation_date_str
        )
        
        # 可选：在高亮旁边添加一个便签注释
        # 获取高亮区域的右上角位置
        annot_point = fitz.Point(inst.x1 + 10, inst.y0)
        sticky_note = page.add_text_annot(annot_point, comment_text, icon="Note")
        sticky_note.set_info(
            title=author,
            content=comment_text,
            creationDate=creation_date_str
        )
    
    # 保存并优化 PDF
    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()
    print(f"✅ 已高亮 '{text_to_highlight}' 并添加注释")
    print(f"   标注者：{author}，时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    return True


def add_rect_highlight_with_comment(input_path, output_path, page_idx, rect_coords, comment_text, author="唐骏涛"):
    """
    高亮指定矩形区域并添加注释
    :param rect_coords: 矩形区域 (x0, y0, x1, y1) 左上角和右下角坐标
    """
    doc = fitz.open(input_path)
    
    if not (0 <= page_idx < len(doc)):
        raise ValueError(f"页码无效，该 PDF 共有 {len(doc)} 页（索引 0~{len(doc)-1}）")
    
    page = doc[page_idx]
    
    # 创建矩形区域
    rect = fitz.Rect(rect_coords)
    
    # 添加高亮
    highlight = page.add_highlight_annot(rect)
    
    # 格式化时间
    now = datetime.now()
    creation_date_str = f"D:{now.strftime('%Y%m%d%H%M%S')}"
    
    # 设置注释
    highlight.set_info(
        title=author,
        content=comment_text,
        creationDate=creation_date_str
    )
    
    # 添加便签注释
    annot_point = fitz.Point(rect.x1 + 10, rect.y0)
    sticky_note = page.add_text_annot(annot_point, comment_text, icon="Note")
    sticky_note.set_info(
        title=author,
        content=comment_text,
        creationDate=creation_date_str
    )
    
    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()
    print(f"✅ 已高亮矩形区域并添加注释")
    print(f"   标注者：{author}，时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    return True


# ================= 使用示例 =================
if __name__ == "__main__":
    INPUT_PDF = "/home/junta/My_Code/Tex_Agent/Trie.pdf"
    
    # 示例1：高亮特定文本并添加注释
    add_highlight_with_comment(
        input_path=INPUT_PDF,
        output_path="output_highlight.pdf",
        page_idx=0,
        text_to_highlight="基本操作",  # 替换为实际文本
        comment_text="这里需要修改\n建议优化算法实现",
        author="唐骏涛"
    )
    
    # 示例2：高亮矩形区域（如果不确定文本位置，可以使用坐标）
    # add_rect_highlight_with_comment(
    #     input_path=INPUT_PDF,
    #     output_path="output_rect_highlight.pdf",
    #     page_idx=0,
    #     rect_coords=(100, 150, 300, 180),  # (x0, y0, x1, y1)
    #     comment_text="这个段落需要review",
    #     author="唐骏涛"
    # )