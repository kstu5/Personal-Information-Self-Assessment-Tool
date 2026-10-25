"""Independent structural reproductions of the observed failures; does not patch the product."""
from pathlib import Path
import json,sys,zipfile,collections
from lxml import etree as E
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
from backend.file_formats import Document
from run_document_audit import checkpoints,write
def main():
    findings=[]
    for name in ('word_structures.docx','word_linebreak.docx'):
        work=HERE/'qa'/'diagnose'/Path(name).stem;work.mkdir(parents=True,exist_ok=True)
        d=Document(HERE/'fixtures'/name,work).load();edits={}
        for p in d.parts:
            value=p['text']
            for token in ('김민수','이지은','010-0000-1234','010-0000-5678','sample@example.invalid','서울특별시 마포구 예시로 12, 302호'):value=value.replace(token,'[삭제]')
            if value!=p['text']:edits[p['id']]=value
        out=work/'adapter_output.docx';d.export(out,edits,[]);again=work/'reread';again.mkdir(exist_ok=True);r=Document(out,again).load();by={json.dumps(p['target'],sort_keys=True):p for p in r.parts};mismatches=[]
        for p in d.parts:
            if p['id'] in edits and json.dumps(p['target'],sort_keys=True) not in by:
                matches=[q for q in r.parts if q['text']==edits[p['id']]]
                mismatches.append({'oldText':p['text'],'expectedText':edits[p['id']],'oldTarget':p['target'],'sameTextRereadTargets':[q['target'] for q in matches]})
        findings.append({'file':name,'adapterExportSucceeded':out.exists(),'verificationTargetMismatches':mismatches})
    path=HERE/'reviewed/hancom_notes__auto_full.hwpx'
    with zipfile.ZipFile(path) as z:
        tree=E.fromstring(z.read('Contents/section0.xml'))
        tails=[{'node':tree.getroottree().getpath(e),'tail':e.tail} for e in tree.iter() if e.tail and '010-0000-1234' in e.tail]
    findings.append({'file':path.name,'missedXMLTails':tails})
    # A detected sheet name can be changed safely when the replacement names are unique.
    from backend.detection import Detector
    from backend.file_review import FileReviewStore
    from tests.test_file_review import wait
    detector=Detector();store=FileReviewStore(detector)
    try:
        source=HERE/'fixtures/xlsx_sheet_names.xlsx';j=store.upload(source.name,source.read_bytes());ready=wait(store,j['id'])
        edits={p['id']:('검토시트'+str(i+1)) for i,p in enumerate(ready['manifest']['parts']) if p['location']=='시트 이름'}
        choices={c['id']:{'mode':'full'} for c in ready['candidates'] if c['location']!='시트 이름'}
        store.export(j['id'],ready['revision'],choices,[],edits);done=wait(store,j['id'])
        saved=False
        if done.get('exportResult'):
            tempout=store.root/'unique_names_output.xlsx';store.save_new(j['id'],tempout)
            out=HERE/'reviewed/xlsx_sheet_names__unique_names.xlsx';out.write_bytes(tempout.read_bytes());saved=out.exists()
        findings.append({'file':'xlsx_sheet_names.xlsx','uniqueSheetNameWorkaround':saved,'error':done.get('error')})
    finally:store.close();detector.close()
    write(HERE/'results/root-causes.json',findings)
    # Checkpoint counts include repeated source occurrences, not merely distinct values.
    manifest=json.loads((HERE/'manifest.json').read_text('utf-8'));changes={
        'word_structures.docx':{'김민수':4,'010-0000-1234':2,'이지은':4,'010-0000-5678':2},
        'xlsx_values.xlsx':{'이지은':2,'010-0000-5678':2},
        'xlsx_sheet_names.xlsx':{'김민수':2,'이지은':3,'010-0000-5678':2},
        'pptx_body.pptx':{'이지은':2,'010-0000-5678':2},
        'hancom_notes.hwpx':{'김민수':2,'이지은':3,'010-0000-1234':3}}
    for case in manifest['cases']:
        for gt in case['checks']:
            if gt['text'] in changes.get(case['file'],{}):gt['count']=changes[case['file']][gt['text']]
        if case['file']=='xlsx_sheet_names.xlsx' and not any(x['text']=='010-0000-5678' for x in case['checks']):case['checks'].append({'text':'010-0000-5678','label':'PHONE','count':2,'scope':None})
    write(HERE/'manifest.json',manifest)
    report=json.loads((HERE/'results/audit.json').read_text('utf-8'))
    cases={c['file']:c for c in manifest['cases']}
    for row in report['cases']:
        job=json.loads((HERE/'results'/(Path(row['file']).stem+'_input_job.json')).read_text('utf-8'));row['checkpoints']=checkpoints(cases[row['file']],job)
    write(HERE/'results/audit.json',report)
    checks=[c for r in report['cases'] if not r['expectedBlock'] for c in r['checkpoints']]
    summary=json.loads((HERE/'results/summary.json').read_text('utf-8'))
    for k,field in [('targetCheckpoints','count'),('fullyDetectedCheckpoints','fullyDetected'),('partiallyDetectedCheckpoints','partiallyDetected'),('notExtractedCheckpoints','notExtracted')]:summary[k]=sum(c[field] for c in checks)
    summary['overextendedExamples']=sum(len(c['overextendedExamples']) for c in checks)
    write(HERE/'results/summary.json',summary)
    print(json.dumps(findings,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
