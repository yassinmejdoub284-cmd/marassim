"""Wire the finance components without reformatting the existing application."""
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
path = root/'src/App.jsx'
text = path.read_text(encoding='utf-8')
marker = "{page === 'accounts' && <Accounts notify={notify} user={user} />}"
extra = "{page === 'reports' && <AdvancedReports api={api} saveFile={file => call('saveFile',file)} notify={notify} />}{page === 'forecast' && <CashForecast api={api} saveFile={file => call('saveFile',file)} notify={notify} Modal={Modal} />}"
if extra not in text:
    assert marker in text
    text = text.replace(marker, marker+extra)
pilot = "  ['PILOTAGE', [['reports', 'Rapports avancés', BarChart3, 'Rapports avancés'], ['forecast', 'Cash-flow prévu', TrendingUp, 'Cash-flow prévu']]],\n"
if text.index(pilot) < text.index("  ['RÉSERVATIONS',"):
    text = text.replace(pilot,'').replace("  ['ÉQUIPE & PARAMÈTRES',",pilot+"  ['ÉQUIPE & PARAMÈTRES',")
path.write_text(text,encoding='utf-8')
for name in ['package.json','package-lock.json']:
    path = root/name
    data = json.loads(path.read_text(encoding='utf-8'))
    data['version'] = '3.1.0'
    if 'packages' in data: data['packages']['']['version'] = '3.1.0'
    if name == 'package.json' and not any(r['from'] == 'GUIDE_RAPPORTS.md' for r in data['build']['extraResources']):
        data['build']['extraResources'].append({'from':'GUIDE_RAPPORTS.md','to':'GUIDE_RAPPORTS.md'})
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
path = root/'server/app.py'
text = path.read_text(encoding='utf-8').replace("'version': '3.0.0'","'version': '3.1.0'")
path.write_text(text,encoding='utf-8')
