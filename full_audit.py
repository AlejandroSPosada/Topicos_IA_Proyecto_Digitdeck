import json, sys
sys.stdout.reconfigure(encoding='utf-8')
nb = json.load(open('Entregables/M1/ENTREGABLE.ipynb', encoding='utf-8'))

# Print ALL cells with full content
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', []))
    print(f'\n{"="*60}')
    print(f'CELL {i:02d} [{cell["cell_type"]}]')
    print(src[:1500])
    if len(src) > 1500:
        print(f'...(+{len(src)-1500} chars)')
