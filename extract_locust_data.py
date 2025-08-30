import re
import json

# Read the HTML file
with open(
    "Locust_2025-08-30-11h31_locustfile.py_http___localhost_8000 (1).html",
    "r",
    encoding="utf-8",
) as f:
    content = f.read()

# Find the JSON in window.templateArgs
match = re.search(r"window\.templateArgs = ({.*)", content, re.DOTALL)
if match:
    json_str = match.group(1)
    # Find the end of the JSON object
    brace_count = 0
    end_pos = 0
    for i, char in enumerate(json_str):
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                end_pos = i
                break
    if end_pos > 0:
        json_str = json_str[: end_pos + 1]
        data = json.loads(json_str)
        print(json.dumps(data, indent=2))
    else:
        print("Could not find end of JSON")
else:
    print("JSON not found")
