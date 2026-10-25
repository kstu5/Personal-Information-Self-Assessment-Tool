"""Smoke-test all twelve synthetic formats using the app's actual file readers.

Does not run the PII model or modify the examples. Raw text remains in local QA.
"""
from pathlib import Path
import json
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.file_formats import Document, SUPPORTED

def main():
    # The production file worker runs here so that the OCR language data resolves.
    os.chdir(ROOT/'.runtime/file-tools')
    folder=ROOT/'test/format-document-examples'
    qa=ROOT/'test/qa/format-documents'
    inputs=sorted((folder/'files').iterdir())
    assert len(inputs)==12 and {p.suffix for p in inputs}==SUPPORTED
    rows=[]
    for path in inputs:
        work=qa/'adapter'/path.stem
        work.mkdir(parents=True,exist_ok=True)
        try:
            doc=Document(path,work).load()
            assert doc.parts, 'No readable text was extracted'
            text='\n'.join(p['text'] for p in doc.parts)
            assert '\ufffd' not in text, 'Replacement characters in extracted text'
            (work/'extracted.txt').write_text(text,encoding='utf-8')
            rows.append({'file':path.name,'app_readable':True,'text_parts':len(doc.parts),'assets':len(doc.assets),
                         'read_only':path.suffix=='.hwp','blockers':doc.blockers,'warnings':doc.warnings})
            print(path.name,'OK',len(doc.parts),'parts',flush=True)
        except Exception as e:
            rows.append({'file':path.name,'app_readable':False,'error':str(e)})
            print(path.name,'FAILED',str(e),flush=True)
    (qa/'adapter-smoke.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert all(r['app_readable'] for r in rows)

if __name__=='__main__':main()
