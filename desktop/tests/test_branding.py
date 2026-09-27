import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from lxml import etree

DESKTOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESKTOP / 'server'))
from app import sync_templates


class BrandingTests(unittest.TestCase):
    def test_contract_content_and_fields_are_preserved(self):
        logo = (DESKTOP / 'assets' / 'marassim-logo.png').read_bytes()
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        for original in (DESKTOP / 'branding' / 'original-templates').glob('*.docx'):
            with self.subTest(template=original.name), ZipFile(original) as old, ZipFile(DESKTOP.parent / 'template' / original.name) as new:
                old_xml = etree.fromstring(old.read('word/document.xml'))
                new_xml = etree.fromstring(new.read('word/document.xml'))
                old_text = old_xml.xpath('//w:t/text()', namespaces=ns)
                new_text = new_xml.xpath('//w:t/text()', namespaces=ns)
                self.assertEqual(re.findall(r'\{\{.*?\}\}', ''.join(old_text)), re.findall(r'\{\{.*?\}\}', ''.join(new_text)))
                self.assertIn(logo, [new.read(n) for n in new.namelist() if n.startswith('word/media/')])
                if original.name.startswith('Bon_'):
                    # Only the three branding paragraphs became a single logo paragraph.
                    def structure(elements):
                        return [[(e.tag, sorted(e.attrib.items()), e.text) for e in node.iter()] for node in elements]
                    self.assertEqual(structure(list(old_xml.find('w:body', ns))[3:]), structure(list(new_xml.find('w:body', ns))[1:]))
                else:
                    self.assertEqual(old_text, new_text)

    def test_existing_factory_templates_upgrade_and_keep_recoverable_original(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / 'template'
            destination.mkdir()
            for original in (DESKTOP / 'branding' / 'original-templates').glob('*.docx'):
                (destination / original.name).write_bytes(original.read_bytes())
            sync_templates(DESKTOP.parent / 'template', destination)
            for original in (DESKTOP / 'branding' / 'original-templates').glob('*.docx'):
                self.assertEqual((destination / original.name).read_bytes(), (DESKTOP.parent / 'template' / original.name).read_bytes())
                self.assertEqual((Path(temp) / 'template-history' / 'before-logo' / original.name).read_bytes(), original.read_bytes())
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.glob('*.docx')}
            sync_templates(DESKTOP.parent / 'template', destination)
            self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.glob('*.docx')})

    def test_customized_templates_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / 'template'
            destination.mkdir()
            for original in (DESKTOP / 'branding' / 'original-templates').glob('*.docx'):
                (destination / original.name).write_bytes(b'customized-document')
            sync_templates(DESKTOP.parent / 'template', destination)
            self.assertTrue(all(p.read_bytes() == b'customized-document' for p in destination.glob('*.docx')))


if __name__ == '__main__':
    unittest.main()
