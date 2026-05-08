"""修复 workflow_checklist_annotate_v2.json 中的模板路径。"""
content = open('config/workflow/workflow_checklist_annotate_v2.json', encoding='utf-8-sig').read()
content = content.replace(
    '${metadata.parse_paper.metadata.markdown_path}',
    '${metadata.parse_paper.metadata.tool_metadata.markdown_path}'
)
content = content.replace(
    '${metadata.parse_paper.metadata.json_path}',
    '${metadata.parse_paper.metadata.tool_metadata.json_path}'
)
open('config/workflow/workflow_checklist_annotate_v2.json', 'w', encoding='utf-8').write(content)
import json, re
d = json.load(open('config/workflow/workflow_checklist_annotate_v2.json', encoding='utf-8'))
print(f'OK, nodes: {len(d["nodes"])}')
paths = set(re.findall(r'\$\{([^}]+)\}', content))
print('Template paths used:')
for p in sorted(paths): print(' ', p)
