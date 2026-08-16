import json

with open('/home/shayneeo/.gemini/antigravity/brain/32f30acf-8729-4b86-9f09-d552d0ce98d2/.system_generated/steps/2705/output.txt') as f:
    text = f.read()

if text.startswith('[IMPORTANT'):
    text = text[text.index('{'):]

data = json.loads(text)
print(f"Total Jira issues found: {len(data['issues'])}\n")
for issue in data['issues']:
    key = issue['key']
    summary = issue['fields'].get('summary', '')
    status = issue['fields']['status']['name']
    assignee = issue['fields']['assignee']['displayName'] if issue['fields'].get('assignee') else 'Unassigned'
    labels = issue['fields'].get('labels', [])
    print(f"{key:10} | {status:12} | {assignee:20} | {summary[:60]}")
