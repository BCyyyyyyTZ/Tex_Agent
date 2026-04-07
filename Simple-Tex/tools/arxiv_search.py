import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from tools.base_tool import BaseTool
from utils.logger import debug

class ArxivSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "search_arxiv"

    @property
    def description(self) -> str:
        return "用于在 arXiv 数据库中检索学术文献。输入关键词，返回相关论文的标题、作者、发布时间和摘要。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索关键词，例如 'LoRA adaptive selection' 或 'video analysis'"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数量，默认值为 3"
                }
            },
            "required": ["query"]
        }

    def execute(self, query: str, max_results: int = 3) -> str:
        debug(f"正在 arXiv 检索关键词: '{query}'...")
        # 为了演示，这里用 urllib 简单调用 arXiv API
        url = f"https://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(query)}&start=0&max_results={max_results}"
        
        try:
            response = urllib.request.urlopen(url)
            xml_data = response.read().decode('utf-8')
            root = ET.fromstring(xml_data)
            debug(f"arXiv API 返回的 XML 数据已解析，正在提取论文信息...")
            
            # XML 命名空间
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            entries = root.findall('atom:entry', ns)
            
            if not entries:
                return "未找到相关文献。"
                
            results = []
            for entry in entries:
                debug(f"处理论文: {entry.find('atom:title', ns).text.strip()}")
                title = entry.find('atom:title', ns).text.replace('\n', ' ').strip()
                summary = entry.find('atom:summary', ns).text.replace('\n', ' ').strip()
                results.append(f"Title: {title}\nSummary: {summary}\n---")
                
            return "\n".join(results)
        except Exception as e:
            return f"检索 arXiv 时发生错误: {str(e)}"