import fitz
from datetime import datetime

from typing import List, Optional

from tools.base_tool import BaseTool
from core.message import ToolResult
from config.settings import settings
from utils.logger import get_logger
import os
import tempfile
import traceback

logger = get_logger(__name__)

class PdfCommentTool(BaseTool):
    """
    pdf 注释工具。

    调用 fitz 进行 pdf 注释，
    返回格式化的注释列表（页码、注释内容）。
    """

    def __init__(self):
        super().__init__(
            name="pdf_comment",
            description="在 pdf 的指定位置添加高亮和注释。",
            input_schema={
                "page_idx": "需要注释的内容所在的页码(从 0 开始)",
                "text": "需要添加高亮的文本",
                "comment": "需要添加的注释内容",
            }
        )

    def fuzzy_search(self, page, target_text):
        """
        模糊搜索：将页面所有单词提取出来，通过滑动窗口匹配目标文本
        """
        # 1. 提取页面所有单词及其位置
        # words 结构: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        words = page.get_text("words")
        target_words = target_text.split()
        if not target_words: return []

        results = []
        # 2. 简单的滑动窗口匹配
        for i in range(len(words) - len(target_words) + 1):
            # 提取窗口内的文本并合并
            window_text = "".join(w[4] for w in words[i : i + len(target_words)])
            target_concat = "".join(target_words)
            
            # 允许一定程度的差异（比如忽略角标字符）
            if target_concat.lower() in window_text.lower() or window_text.lower() in target_concat.lower():
                # 合并该窗口内所有单词的矩形框
                rect = words[i][0:4] # 取第一个词的坐标
                for j in range(i + 1, i + len(target_words)):
                    rect = fitz.Rect(rect) | fitz.Rect(words[j][0:4]) # 取并集矩形
                results.append(rect)
                
        return results

    def run_single(self, pdf_path, output_path, page_idx, text, comment, author = None):
        """
        高亮 PDF 中的文本并添加注释
        :param pdf_path: 原始 PDF 路径
        :param output_path: 输出 PDF 路径
        :param page_idx: 页码（从 0 开始）
        :param text: 要高亮的文本内容
        :param comment: 注释内容
        :param author: 标注者名称
        """
        
        base_path = output_path if output_path and os.path.exists(output_path) else pdf_path
        same_file = os.path.abspath(base_path) == os.path.abspath(output_path)
        temp_path = None
        
        try:
            # 如果是同一个文件，创建临时文件
            if same_file:
                temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf')
                os.close(temp_fd)
                save_path = temp_path
            else:
                save_path = output_path
            
            # 打开 PDF
            doc = fitz.open(base_path)
            
            if not (0 <= page_idx < len(doc)):
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"页码{page_idx}无效，该 PDF 共有 {len(doc)} 页（索引 0~{len(doc)-1}）",
                )

            page = doc[page_idx]
            
            # 查找要高亮的文本
            text_instances = page.search_for(text)
            
            if not text_instances:
                doc.close()
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"未找到要高亮注释的文本: '{text}'，在页码{page_idx}未找到",
                )
            
            # 格式化时间
            now = datetime.now()
            creation_date_str = f"D:{now.strftime('%Y%m%d%H%M%S')}"
            
            # 为每个找到的文本实例添加高亮和注释
            for inst in text_instances:
                # 添加高亮
                highlight = page.add_highlight_annot(inst)
                highlight.set_info(
                    #title=author,
                    content=comment,
                    #creationDate=creation_date_str
                )
                
                # 可选：在高亮旁边添加一个便签注释
                # 获取高亮区域的右上角位置
                annot_point = fitz.Point(inst.x1 + 10, inst.y0)
                sticky_note = page.add_text_annot(annot_point, comment, icon="Note")
                sticky_note.set_info(
                    #title=author,
                    content=comment,
                    #creationDate=creation_date_str
                )
            
            # 保存并优化 PDF
            doc.save(save_path, garbage=4, deflate=True, clean=True)
            doc.close()
            
            # 如果是同一个文件，用临时文件替换原文件
            if same_file:
                os.replace(temp_path, output_path)
            
            print(f"✅ 已高亮 '{text}' 并添加注释")
            #print(f"   标注者：{author}，时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
            return ToolResult(
                success=True,
                output= f"已高亮第 {page_idx} 页的 '{text}' 并添加注释 '{comment}'",
            )
        except Exception as e:
            traceback.print_exc()
            # 清理临时文件
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return ToolResult(
                success=False,
                output="处理失败",
                error=f"处理 PDF 时出错: {str(e)}",
            )

    def run(self, pdf_path, output_path, question_list, author=None):
        """
        批量高亮 PDF 中的文本并添加注释
        :param pdf_path: 原始 PDF 路径
        :param output_path: 输出 PDF 路径
        :param question_list: 问题列表，每个字典包含 page_idx, text, comment 三个项
        :param author: 标注者名称
        """
        
        base_path = output_path if output_path and os.path.exists(output_path) else pdf_path
        same_file = os.path.abspath(base_path) == os.path.abspath(output_path)
        temp_path = None
        
        try:
            # 如果是同一个文件，创建临时文件
            if same_file:
                temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf')
                os.close(temp_fd)
                save_path = temp_path
            else:
                save_path = output_path
            
            # 打开 PDF
            doc = fitz.open(base_path)
            
            # 格式化时间
            now = datetime.now()
            creation_date_str = f"D:{now.strftime('%Y%m%d%H%M%S')}"
            
            # 处理每个问题
            success_count = 0
            error_messages = []
            
            # 存储每页找不到文本的注释
            page_not_found_comments = {}
            commented_pages = set()
            
            for i, question in enumerate(question_list):
                try:
                    page_idx = question.get('page_idx')
                    text = question.get('text')
                    comment = question.get('comment')
                    
                    # 验证参数
                    if page_idx is None or text is None or comment is None:
                        error_messages.append(f"问题 {i+1}: 缺少必要参数")
                        continue

                    page_idx -= 1
                    
                    # 检查页码是否有效
                    if not (0 <= page_idx < len(doc)):
                        error_messages.append(f"问题 {i+1}: 页码 {page_idx+1} 无效，该 PDF 共有 {len(doc)} 页")
                        continue
                    
                    page = doc[page_idx]
                    
                    # 查找要高亮的文本
                    text_instances = page.search_for(text)
                    
                    if not text_instances:
                        text_instances = self.fuzzy_search(page, text)
                        if not text_instances:
                            # 记录找不到文本的注释
                            if page_idx not in page_not_found_comments:
                                page_not_found_comments[page_idx] = []
                            page_not_found_comments[page_idx].append(f"问题 {i+1}:\n文本:'{text}'\n注释: {comment}")
                            success_count += 1
                            print(f"✅ 已处理问题 {i+1}")
                            continue
                    
                    # 为每个找到的文本实例添加高亮和注释
                    for inst in text_instances:
                        # 添加高亮
                        highlight = page.add_highlight_annot(inst)
                        highlight.set_info(
                            content=f"问题 {i+1}: {comment}",
                        )
                        
                        # 在高亮旁边添加一个便签注释
                        annot_point = fitz.Point(inst.x1 + 10, inst.y0)
                        sticky_note = page.add_text_annot(annot_point, comment, icon="Note")
                        sticky_note.set_info(
                            content=comment,
                        )
                    
                    success_count += 1
                    commented_pages.add(page_idx + 1)
                    print(f"✅ 已处理问题 {i+1}")
                    
                except Exception as e:
                    error_messages.append(f"问题 {i+1}: 处理失败 - {str(e)}")
            
            # 为每页添加找不到文本的汇总注释
            for page_idx, comments in page_not_found_comments.items():
                if comments:
                    page = doc[page_idx]
                    # 构建汇总注释内容
                    comment_content = "\n\n".join(comments)
                    # 在页面左上角添加汇总注释
                    annot_point = fitz.Point(50, 50)  # 固定位置
                    sticky_note = page.add_text_annot(annot_point, comment_content, icon="Note")
                    sticky_note.set_info(
                        content=comment_content,
                    )
            
            # 保存并优化 PDF
            doc.save(save_path, garbage=4, deflate=True, clean=True)
            doc.close()
            
            # 如果是同一个文件，用临时文件替换原文件
            if same_file:
                os.replace(temp_path, output_path)
            
            print(f"\n📋 批量处理完成")
            print(f"   成功: {success_count} 个问题")
            print(f"   失败: {len(error_messages)} 个问题")
            if error_messages:
                print(f"   错误信息: {'; '.join(error_messages)}")
            print(f"   标注者：{author}，时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 构建输出消息
            output_message = f"已成功处理 {success_count} 个问题"
            if error_messages:
                output_message += f"，{len(error_messages)} 个问题处理失败"
            
            return ToolResult(
                success=success_count > 0,
                output=output_message,
                metadata={
                    "success_count": success_count,
                    "total_count": len(question_list),
                    "error_count": len(error_messages),
                    "error_messages": error_messages,
                    "commented_pages": commented_pages
                }
            )
            
        except Exception as e:
            traceback.print_exc()
            # 清理临时文件
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return ToolResult(
                success=False,
                output="处理失败",
                error=f"批量处理 PDF 时出错: {str(e)}",
            )


if __name__ == "__main__":
    tool = PdfCommentTool()
    
    # 测试单个标注
    # tool.run(
    #     pdf_path=r"C:/Users/86138/Downloads/AutoGen Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework_copy.pdf",
    #     output_path=r"C:/Users/86138/Downloads/AutoGen Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework_copy.pdf",
    #     page_idx=0,
    #     text="AutoGen",
    #     comment="这是一个注释",
    #     author="TestUser",
    # )
    
    # 测试批量标注
    question_list = [
        {
            "page_idx": 0,
            "text": "TEST",
            "comment": "这是第一个注释"
        },
        {
            "page_idx": 0,
            "text": "Framework",
            "comment": "这是第二个注释"
        }
    ]
    
    tool.run(
        pdf_path=r"C:/Users/86138/Downloads/AutoGen Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework_copy.pdf",
        output_path=r"C:/Users/86138/Downloads/AutoGen Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework_copy.pdf",
        question_list=question_list,
        author="TestUser"
    )
