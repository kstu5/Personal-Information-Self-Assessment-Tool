"""Check the consistency and structural readability of delivered test artifacts."""
from pathlib import Path
import hashlib,json,zipfile
from lxml import etree as E
HERE=Path(__file__).resolve().parent
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    data=json.loads((HERE/'results/audit.json').read_text('utf-8'));hashes=json.loads((HERE/'results/fixture-hashes.json').read_text('utf-8'));checks=[]
    assert len(data['cases'])==len(hashes)==21
    for name,h in hashes.items():assert digest(HERE/'fixtures'/name)==h
    assert all(r['originalUnchanged'] and not r.get('harnessError') for r in data['cases'])
    for row in data['cases']:
        row['sourceSHA256']=hashes[row['file']]
        for key in ('autoFull','manualRepair','selective','custom'):
            result=row.get(key,{})
            if result.get('saved'):
                p=HERE/result['file'];assert digest(p)==result['sha256'];checks.append(result['file'])
                if p.suffix=='.docx':
                    from docx import Document
                    Document(p)
                elif p.suffix=='.pptx':
                    from pptx import Presentation
                    assert len(Presentation(p).slides)==2
                elif p.suffix=='.xlsx':
                    from openpyxl import load_workbook
                    w=load_workbook(p);assert not any(c.data_type=='f' for s in w for row in s for c in row)
                elif p.suffix=='.hwpx':
                    with zipfile.ZipFile(p) as z:
                        assert z.testzip() is None
                        assert not any(n.startswith('Preview/') for n in z.namelist())
                        for n in z.namelist():
                            if n.endswith(('.xml','.rels','.hpf')):E.fromstring(z.read(n))
                elif p.suffix=='.pdf':
                    import pymupdf as fitz
                    with fitz.open(p) as d:assert len(d)==1 and not d.metadata['author']
            if result.get('assertions'):assert all(result['assertions'].values())
    assert all(r.get('exportRefusalStatus',400)!=200 for r in data['cases'] if r['expectedBlock'])
    causes=json.loads((HERE/'results/root-causes.json').read_text('utf-8'))
    assert causes[-1]['uniqueSheetNameWorkaround']
    (HERE/'results/audit.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    result={'fixtureHashesVerified':len(hashes),'savedCopiesWithVerifiedHashes':len(checks),'savedCopiesOpenedStructurally':len(checks),'selectiveAndCustomAssertionsPassed':True,'allOriginalsUnchanged':True,'uniqueSheetNameWorkaroundPassed':True}
    (HERE/'results/artifact-integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    authoring=HERE/'qa/authoring';authoring.mkdir(parents=True,exist_ok=True)
    for p in (HERE/'fixtures').glob('*.inspect.ndjson'):p.replace(authoring/p.name)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
