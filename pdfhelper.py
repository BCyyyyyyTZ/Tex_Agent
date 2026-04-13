import fitz  # PyMuPDF 的导入名

def add_comment_to_pdf(input_path, output_path, page_idx, text, x, y, annot_type="sticky"):
    """
    向 PDF 指定页面添加注释
    :param input_path: 原始 PDF 路径
    :param output_path: 输出 PDF 路径
    :param page_idx: 页码（从 0 开始）
    :param text: 注释内容
    :param x, y: 注释位置坐标（单位：点 pt，1pt = 1/72 英寸）
    :param annot_type: 注释类型 "sticky"（便签/气泡） 或 "freetext"（直接显示文本）
    """
    # 打开 PDF
    doc = fitz.open(input_path)
    
    if not (0 <= page_idx < len(doc)):
        raise ValueError(f"页码无效，该 PDF 共有 {len(doc)} 页（索引 0~{len(doc)-1}）")
        
    page = doc[page_idx]
    
    if annot_type == "sticky":
        # 添加便签式注释（点击气泡可看内容）
        point = fitz.Point(x, y)
        page.add_text_annot(point, text, icon="Comment")
    elif annot_type == "freetext":
        # 添加自由文本注释（直接显示在页面上）
        rect = fitz.Rect(x, y, x + 200, y + 30)  # 矩形区域：左、上、右、下
        page.add_freetext_annot(rect, text, fontsize=11, fontname="helv", 
                                text_color=(0, 0, 1), align=fitz.TEXT_ALIGN_LEFT)
    else:
        raise ValueError("annot_type 必须是 'sticky' 或 'freetext'")
        
    # 保存并优化 PDF
    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()
    print(f"✅ 注释已成功添加至：{output_path}")

# ================= 使用示例 =================
if __name__ == "__main__":
    INPUT_PDF  = "/home/junta/My_Code/Tex_Agent/01stack.pdf"
    OUTPUT_PDF = "output_with_comment.pdf"
    
    # 在第 1 页（索引 0），坐标 (100, 150) 处添加一个气泡注释
    add_comment_to_pdf(
        input_path=INPUT_PDF,
        output_path=OUTPUT_PDF,
        page_idx=0,
        text="这是自动插入的测试注释\n支持换行和中文。",
        x=100, y=150,
        annot_type="sticky"  # 改为 "freetext" 可显示为直接文本
    )