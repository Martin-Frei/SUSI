import os
import re

docs_dir = r"C:\Users\tsinn\VSCode\Repos\SUSI_neu\docs"
pattern = re.compile(r"10\.06\.2026")

outdated = []

for root, dirs, files in os.walk(docs_dir):
    for file in files:
        if file.endswith(".md"):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(filepath, encoding="latin-1") as f:
                    content = f.read()
            
            if not pattern.search(content):
                rel = os.path.relpath(filepath, docs_dir)
                outdated.append(rel)

print(f"\n{len(outdated)} Dateien ohne '10.06.2026':\n")
for f in sorted(outdated):
    print(f"  {f}")