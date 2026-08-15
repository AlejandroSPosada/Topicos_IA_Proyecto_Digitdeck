import json, sys
sys.stdout.reconfigure(encoding='utf-8')
nb = json.load(open('Entregables/M1/ENTREGABLE.ipynb', encoding='utf-8'))

celdas_de_interes = [6, 14, 23, 24, 25, 34, 35, 60]
for i in celdas_de_interes:
    cell = nb['cells'][i]
    src = ''.join(cell.get('source', []))
    print(f'\n=== CELL {i} [{cell["cell_type"]}] ===')
    print(src[:700])
    if len(src) > 700:
        print('...(truncado)')
