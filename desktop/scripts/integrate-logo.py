"""Apply the supplied logo without changing contract fields or business text."""
import hashlib
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from docx import Document
from docx.shared import Inches
from PIL import Image, ImageOps
from lxml import etree

DESKTOP = Path(__file__).resolve().parents[1]
TEMPLATES = DESKTOP.parent / 'template'
LOGO = DESKTOP / 'assets' / 'marassim-logo.png'
LOGO_SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else LOGO
ORIGINALS = DESKTOP / 'branding' / 'original-templates'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    LOGO.parent.mkdir(exist_ok=True)
    ORIGINALS.mkdir(parents=True, exist_ok=True)
    if LOGO_SOURCE.resolve() != LOGO.resolve():
        shutil.copyfile(LOGO_SOURCE, LOGO)
    # Format conversion for the Windows application icon; original PNG is retained.
    icon = ImageOps.pad(Image.open(LOGO).convert('RGBA'), (256, 256), method=Image.Resampling.LANCZOS, color='white')
    icon.save(DESKTOP / 'build' / 'marassim.ico', format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)])
    manifest = {'version': 1, 'files': {}}
    for name in ['Bon_Recu_Marassim_Template.docx', 'Contrat_Arabe_Template.docx']:
        target, original = TEMPLATES / name, ORIGINALS / name
        if not original.exists():
            shutil.copyfile(target, original)
        if name.startswith('Bon_'):
            document = Document(original)
            brand = document.paragraphs[:3]
            brand[0].clear()
            picture = brand[0].add_run().add_picture(str(LOGO), width=Inches(.85))
            picture._inline.docPr.set('descr', 'Logo Marassim')
            brand[0].paragraph_format.space_after = brand[2].paragraph_format.space_after
            for paragraph in brand[1:]:
                paragraph._p.getparent().remove(paragraph._p)
            document.save(target)
        else:
            with ZipFile(original) as archive:
                items = [(entry, archive.read(entry.filename)) for entry in archive.infolist()]
            with ZipFile(target, 'w', compression=ZIP_DEFLATED) as archive:
                for entry, data in items:
                    if entry.filename == 'word/media/image1.png':
                        data = LOGO.read_bytes()
                    elif entry.filename == 'word/document.xml':
                        root = etree.fromstring(data)
                        namespaces = {'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing', 'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
                        drawing = root.xpath('//wp:anchor', namespaces=namespaces)[0]
                        extent = drawing.find('wp:extent', namespaces)
                        height = str(round(int(extent.get('cx')) * 148 / 156))
                        extent.set('cy', height)
                        for ext in drawing.xpath('.//a:xfrm/a:ext', namespaces=namespaces):
                            ext.set('cy', height)
                        drawing.find('wp:docPr', namespaces).set('descr', 'Logo Marassim')
                        data = etree.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
                    archive.writestr(entry, data)
        manifest['files'][name] = {'previous_sha256': [sha(original.read_bytes())], 'sha256': sha(target.read_bytes())}
    (TEMPLATES / 'branding.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Logo and both templates updated. Originals preserved in desktop/branding/original-templates.')

if __name__ == '__main__':
    main()
