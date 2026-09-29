import os

def replace_in_file(filepath, replacements):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_content = content
        for old, new in replacements:
            new_content = new_content.replace(old, new)
            
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated {filepath}")
    except Exception as e:
        print(f"Error {filepath}: {e}")

replacements_list = [
    # Model property changes
    ("Item.size", "Item.barcode"),
    ("item.size", "item.barcode"),
    ("Item.pattern", "Item.name"),
    ("item.pattern", "item.name"),
    ("Item.type", "Item.description"),
    ("item.type", "item.description"),
    
    # Form input field names
    ("name=\"size\"", "name=\"barcode\""),
    ("name=\"pattern\"", "name=\"name\""),
    ("name=\"type\"", "name=\"description\""),
    
    # Python file param parsing in routes
    ("size: str = Form(\"\")", "barcode: str = Form(\"\")"),
    ("pattern: str = Form(\"\")", "name: str = Form(\"\")"),
    ("type: str = Form(\"\")", "description: str = Form(\"\")"),
    
    ("item.size = size", "item.barcode = barcode"),
    ("item.pattern = pattern", "item.name = name"),
    ("item.type = type", "item.description = description"),
    
    ("Size", "Barcode"),
    ("Pattern", "Product Name"),
    ("Type", "Description"),
    
    ("Tubeless / Tube-type", "Sanitary description"),
    ("175/65 R14", "e.g. 1234567890"),
]

for root, dirs, files in os.walk('d:/sanitary store/app'):
    if '__pycache__' in root:
        continue
    for file in files:
        if file.endswith(('.html', '.py')):
            replace_in_file(os.path.join(root, file), replacements_list)

print("Template updates complete.")
