import os

replacements = [
    ("Arshaf Sanitary Store", "Arshaf Sanitary Store"),
    ("arshaf-sanitary-store", "arshaf-sanitary-store"),
    ("ARSHAF SANITARY STORE", "ARSHAF SANITARY STORE"),
    ("Sanitary Store Management System", "Sanitary Store Management System"),
    ("sanitary store", "sanitary store"),
    ("Sanitary Store", "Sanitary Store"),
]

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        return
    
    new_content = content
    for old, new in replacements:
        new_content = new_content.replace(old, new)
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for root, dirs, files in os.walk('d:/sanitary store'):
    if 'venv' in root or '.git' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith(('.py', '.html', '.md', '.json', '.yaml', '.txt', '.css', '.js')):
            process_file(os.path.join(root, file))

print("Replacement complete.")
