"""Extract unchanged Excel writers from Tkinter; remove only GUI/file dialogs."""
import ast
import textwrap
from pathlib import Path

root = Path(__file__).resolve().parents[2]
source = (root / 'gui.py').read_text('utf-8')
tree = ast.parse(source)
output = ['"""Excel layouts copied unchanged from the existing Tkinter application.\nRegenerate with scripts/extract-legacy-exports.py after an intentional legacy change.\n"""', 'from datetime import datetime', 'from types import SimpleNamespace', 'import openpyxl', 'from openpyxl.styles import Font, Alignment, PatternFill, Border, Side', '']
for name, function in [('JournalCaisseTab', '_write_tawfik'), ('JournalCaisseOmarTab', '_write_omar')]:
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_export_excel')
    body = ast.get_source_segment(source, method)
    begin = body.index('        wb = openpyxl.Workbook()')
    end = body.index('        wb.save(path)') + len('        wb.save(path)')
    output += [f'def {function}(self, path):', textwrap.indent(textwrap.dedent(body[begin:end]), '    '), '']
output += ['''def export_journal(database, omar, start, end, path, number='?'):
    def fmt(value):
        return datetime.strptime(value, '%Y-%m-%d').strftime('%d/%m/%Y') if value else ''
    days = ['LUNDI', 'MARDI', 'MERCREDI', 'JEUDI', 'VENDREDI', 'SAMEDI', 'DIMANCHE']
    day = lambda value: days[datetime.strptime(value, '%Y-%m-%d').weekday()]
    data = (database.get_journal_caisse_omar if omar else database.get_journal_caisse)(start, end)
    header = f"Journal de Caisse{' Omar' if omar else ''} N°{number}  —  {day(start)} {fmt(start)}  au  {day(end)} {fmt(end)}"
    data.update(header=header, debut=start, fin=end)
    stub = SimpleNamespace(_last_data=data, _fmt_date=fmt)
    (_write_omar if omar else _write_tawfik)(stub, path)
''']
(root / 'desktop/server/legacy_exports.py').write_text('\n'.join(output), 'utf-8')
