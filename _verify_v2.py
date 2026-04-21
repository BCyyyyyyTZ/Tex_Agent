import json, re, sys
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(open('config/workflow_checklist_annotate_v2.json', encoding='utf-8'))
n = len(d['nodes'])
print(f'OK nodes={n}')
text = open('config/workflow_checklist_annotate_v2.json', encoding='utf-8').read()
paths = set(re.findall(r'\$\{([^}]+)\}', text))
for p in sorted(paths):
    print(' ', p)
