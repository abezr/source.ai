#!/usr/bin/env python3
"""
Fix indentation issue in main.py
"""

with open("src/main.py", "r") as f:
    content = f.read()

# Fix the indentation issue by replacing the indented decorator
content = content.replace(
    '    \n    \n    @app.get("/books/{book_id}/toc"',
    '\n\n@app.get("/books/{book_id}/toc"',
)

with open("src/main.py", "w") as f:
    f.write(content)

print("Fixed indentation issue in main.py")
