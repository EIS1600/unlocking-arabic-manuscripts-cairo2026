#!/usr/bin/env python3
"""Build self-contained, manually saved workshop reviews from packaged evidence.

Usage (from the workshop directory; Python standard library only):
  python3 scripts/build_portable_review.py
  python3 scripts/build_portable_review.py --check

Reads only packaged _html_review HTML and proposal JS. Never imports browser/file
drafts, review_output, ground truth, or original production files. The root
index.html loads consensus documents on demand. Saved HTML and the optional
review files are self-contained. No API requests are made.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

WORKSHOP = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent
LUNA_RUN = 'cairo-workshop-luna-waw-20260927'
TITLES = {
    'printed-books': 'Cairo2026 · Printed books',
    'printed-books-consensus': 'Cairo2026 · Printed books — consensus review',
    'printed-books-luna': 'Cairo2026 · Printed books — Luna-assisted review',
    'experiment-manuscripts': 'Cairo2026 · Manuscripts — experimental review',
}


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


class IndexLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.attributes = {}
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'review-link' in attrs.get('class', '').split():
            self.current = [attrs['href'], '']
            self.attributes[attrs['href']] = attrs

    def handle_data(self, text):
        if self.current is not None:
            self.current[1] += text

    def handle_endtag(self, tag):
        if tag == 'a' and self.current is not None:
            self.links.append(tuple(self.current))
            self.current = None


def local_target(index, href, root):
    url = urlsplit(href)
    if url.scheme or url.netloc:
        raise ValueError('External review dependency: ' + href)
    path = (index.parent / unquote(url.path)).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Missing or escaping review dependency: ' + href)
    return path


def embedded_data(text):
    start = text.index('const DATA = ') + len('const DATA = ')
    return json.JSONDecoder().raw_decode(text[start:])[0]


def config_for(index, fragment, root):
    query = parse_qs(fragment)
    if 'agent-review' not in query:
        return None
    source = index.read_text()
    routes = json.JSONDecoder().raw_decode(source.split('const agentConfigs = ', 1)[1])[0]
    route = routes[query['document'][0]]
    path = local_target(index, route['config_script'], root)
    config = json.JSONDecoder().raw_decode(path.read_text().split('] = ', 1)[1])[0]
    if config['run_id'] != query['agent-review'][0] or config['document'] != query['document'][0] or config['mode'] != 'human':
        raise ValueError('Mismatched suggestion configuration')
    return config


def adapt_document(text, config=None):
    """Keep original editing/export logic but disable both persistence mechanisms."""
    data = embedded_data(text)
    if config and (config['evidence_fingerprint'] != data['agent_evidence_fingerprint'] or not data.get('agent_normalised')):
        raise ValueError('Proposal evidence does not match the packaged OCR viewer')
    text = re.sub(r'<link\b[^>]*href="https?://[^>]*>', '', text)
    text = text.replace('window.localStorage', 'workshopStorage').replace('localStorage.', 'workshopStorage.')
    prefix = 'let workshopRestoring=true;\nconst workshopStorage={getItem(){return null;},setItem(){},removeItem(){}};\n'
    text = text.replace('const DATA = ', prefix + 'const DATA = ', 1)
    start = text.find('const agentRequest = new URLSearchParams(')
    if start >= 0:
        end = text.index('let agentReview = null;', start)
        bootstrap = ''
        if config:
            namespace = 'consensus' if config.get('review_kind') == 'consensus' else 'agent'
            runtime = {
                'agent_review': {**config, 'dataset_index': True},
                'review_instance_id': f"{namespace}:{config['run_id']}:{config['document']}:{config['source_fingerprint']}:{config['decision_fingerprint']}:{config['mode']}",
                'review_state_path': config['verification_path'],
            }
            bootstrap = 'Object.assign(DATA,' + encode(runtime) + ');\n'
        text = text[:start] + bootstrap + text[end:]
    elif config:
        raise ValueError('Missing proposal bootstrap')
    bridge = (ASSETS / 'portable_bridge.js').read_text()
    marker = '\ninitializeStandaloneAutosave();'
    if text.count(marker) != 1:
        raise ValueError('Unexpected reviewer initialization')
    text = text.replace(marker, '\n' + bridge + '\ninitializeStandaloneAutosave();')
    text = text.replace('</style>', '\n#connectDatasetBtn,#autosaveStatus,.autosave-separator{display:none!important}\n</style>', 1)
    text = re.sub(r'<p><strong>Browser requirement:</strong>.*?</p>', '<p>This workshop review has no autosave. Use <strong>Save HTML</strong> in the left sidebar before closing.</p>', text, count=1, flags=re.S)
    saving = '''<h3>Save and export</h3><ul>
    <li><strong>Save HTML</strong> in the left sidebar downloads the entire review with its images and current corrections. Reopen that downloaded HTML to resume, then save again after further edits. No folder connection or JSON import is needed. The first save from the website also downloads unopened documents and may take longer.</li>
    <li>There is no autosave. Keep your latest downloaded copy. Switching documents retains edits only within this open session.</li>
    <li><strong>Export</strong> downloads metadata or transcription, not the editable application. Export JSON retains text, geometry and review status; Export Markdown contains the transcription and structural markers.</li>
    <li><strong>Validate</strong> checks unresolved words and layout problems. Use <strong>Mark Reviewed</strong> only after checking the document. Saving HTML neither confirms suggestions nor marks the document as reviewed.</li>
    </ul>'''
    text = re.sub(r'<h3>Validate, autosave, and export</h3>.*?(?=<h3>Navigate and adjust)', saving+'\n', text, count=1, flags=re.S)
    text = text.replace("Google Chrome's browser shortcuts", "Your browser's shortcuts")
    return text


def documents_from(index, root):
    parser = IndexLinks()
    parser.feed(index.read_text())
    documents = []
    for href, label in parser.links:
        path = local_target(index, href, root)
        original = path.read_text()
        kind = 'ocr' if 'const FILE_STEM =' in original else 'metadata'
        config = config_for(index, urlsplit(href).fragment, root)
        attrs = parser.attributes[href]
        status = next((item for item in attrs.get('class', '').split() if item in ('ocr-unresolved', 'ocr-resolved')), '')
        documents.append({'id': hashlib.sha256(href.encode()).hexdigest()[:16], 'label': label if kind == 'ocr' else 'Bibliographic metadata', 'kind': kind, 'status_class': status, 'status_text': attrs.get('title', ''), 'html': adapt_document(original, config)})
    if not documents:
        raise ValueError('Index has no review documents: ' + str(index))
    return documents


def render_bundle(documents, name, *, identity=None):
    identity = identity or hashlib.sha256(encode(documents).encode()).hexdigest()
    resources = {'id': identity, 'filename': name + '.html', 'documents': documents}
    initial = next((doc for doc in documents if doc['kind'] == 'ocr'), documents[0])
    state = {'schema': 'cairo_workshop_session', 'version': 1, 'bundle': identity, 'active': initial['id'], 'drafts': {}, 'saved_at': None}
    template = (ASSETS / 'portable_review.html').read_text()
    # Reuse the actual original combined review's stylesheet, not a redesign.
    original = sources(WORKSHOP / 'review')['printed-books-consensus'].read_text()
    style = re.search(r'<style>(.*?)</style>', original, re.S)[1]
    return (template.replace('__TITLE__', escape(TITLES[name]))
            .replace('__STYLE__', style)
            .replace('__SCRIPT__', (ASSETS / 'portable_review.js').read_text())
            .replace('__RESOURCES__', encode(resources)).replace('__STATE__', encode(state)))


def sources(root):
    printed = root / 'cairo2026_dataset/_html_review'
    consensus = list((printed / 'consensus').glob('*/index.html'))
    if len(consensus) != 1:
        raise ValueError('Expected exactly one packaged consensus branch')
    return {
        'printed-books': printed / 'cairo2026_dataset_google-document-ai.html',
        'printed-books-consensus': consensus[0],
        'printed-books-luna': printed / 'agent' / LUNA_RUN / 'index.html',
        'experiment-manuscripts': root / 'cairo2026_dataset_mss/_html_review/cairo2026_dataset_mss_manuscript.html',
    }


def main_exercise_documents(documents):
    """The online exercise contains only the first two OCR books, no metadata."""
    selected = [doc for doc in documents if doc['kind'] == 'ocr'][:2]
    if len(selected) != 2:
        raise ValueError('The main workshop exercise requires two OCR books')
    return selected


def build(workshop=WORKSHOP, check=False):
    root = workshop / 'review'
    for name, index in sources(root).items():
        documents = documents_from(index, root)
        output = render_bundle(documents, name)
        targets = [root / (name + '.html')]
        for target in targets:
            if check:
                if not target.is_file() or target.read_text() != output:
                    raise ValueError('Portable review needs rebuilding: ' + str(target))
            else:
                target.write_text(output)
            print(f'{target.relative_to(workshop)}: {len(documents)} views, {len(output.encode()) / 1024**2:.1f} MiB')
        if name == 'printed-books-consensus':
            online_documents = main_exercise_documents(documents)
            manifest = []
            for doc in online_documents:
                digest = hashlib.sha256(doc['html'].encode()).hexdigest()
                relative = f'review/assets/{digest}.js'
                target = workshop / relative
                payload = 'window.workshopDocumentLoaded(' + encode(digest) + ',' + encode(doc['html']) + ');\n'
                if check:
                    if not target.is_file() or target.read_text() != payload:
                        raise ValueError('Missing or outdated online document: ' + str(target))
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(payload)
                manifest.append({k: v for k, v in doc.items() if k != 'html'} | {'url': relative, 'digest': digest})
            online = render_bundle(manifest, name, identity=hashlib.sha256(encode(online_documents).encode()).hexdigest())
            target = workshop / 'index.html'
            if check:
                if not target.is_file() or target.read_text() != online:
                    raise ValueError('Online index needs rebuilding')
            else:
                target.write_text(online)
            print(f'index.html: {len(online.encode()) / 1024:.1f} KiB; documents loaded on selection')
            if not check:
                used = {Path(doc['url']).name for doc in manifest}
                for previous in (root / 'assets').glob('*.js'):
                    if previous.name not in used and re.fullmatch(r'[0-9a-f]{64}\.js', previous.name):
                        if previous.read_text().startswith('window.workshopDocumentLoaded('):
                            previous.unlink()  # Only this generator's superseded, reproducible assets.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify packaged outputs without modifying them')
    build(check=parser.parse_args().check)


if __name__ == '__main__':
    main()
