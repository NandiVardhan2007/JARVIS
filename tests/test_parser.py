import re
import json

patterns = [
    '<function=recall_memory {"query": "user information"} </function>',
    '<function=recall_memory({"query": "user information"})</function>',
    '<function=recall_memory {"query": "user information"}</function>',
    '<function=recall_memory{"query": "user information"}</function>',
    '<function=open_application {"app_name": "whatsapp"}> </function>'
]

def parse(text):
    m = re.search(r"<function=(\w+)[\s\(]*(\{.*?\})[\s\)]*(?:>)?(?:</function>)?", text, re.DOTALL)
    if m:
        return m.group(1), json.loads(m.group(2))
    return None

for p in patterns:
    print("Parsed:", parse(p))
