"""Comprueba que todas las celdas de código del notebook son Python válido (ignorando los comandos '!').

Uso:  python tests/test_notebook_compila.py
"""
import ast
import os

import nbformat

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
nb = nbformat.read(os.path.join(ROOT, 'notebooks', 'StrokeLab_v3_pipeline.ipynb'), 4)
for i, c in enumerate(nb.cells):
    if c.cell_type == 'code':
        src = '\n'.join(l for l in c.source.splitlines() if not l.lstrip().startswith('!'))
        try:
            ast.parse(src)
        except SyntaxError as e:
            raise SystemExit(f'Celda {i} con error de sintaxis: {e}')
print('OK: todas las celdas compilan')
