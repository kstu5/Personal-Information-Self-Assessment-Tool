"""Focused follow-up review. Adds evidence only; does not modify product code."""
from pathlib import Path
import json,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'validation'))
from lxml import etree as E
from fastapi.testclient import TestClient
from backend.app import create_app
from run_document_audit import external_audit,sha

def main():
    here=ROOT/'validation/additional-review';here.mkdir(exist_ok=True)
    template=ROOT/'validation/fixtures/word_repeated.docx'
    filename_case=here/'김민수_010-0000-1234_안내.docx';filename_case.write_bytes(template.read_bytes())
    with zipfile.ZipFile(template) as z:entries={n:z.read(n) for n in z.namelist()}
    ns='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    tree=E.fromstring(entries['word/document.xml']);body=tree.find('{'+ns+'}body')
    for node in list(body):
        if E.QName(node).localname!='sectPr':body.remove(node)
    para=E.Element('{'+ns+'}p');field=E.SubElement(para,'{'+ns+'}fldSimple');field.set('{'+ns+'}instr','HYPERLINK "mailto:sample@example.invalid"')
    run=E.SubElement(field,'{'+ns+'}r');E.SubElement(run,'{'+ns+'}t').text='문의하기';body.insert(0,para)
    entries['word/document.xml']=E.tostring(tree,xml_declaration=True,encoding='UTF-8')
    simple_case=here/'simple_hyperlink.docx'
    with zipfile.ZipFile(simple_case,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in entries.items():z.writestr(n,b)
    report=[];app=create_app(19265)
    with TestClient(app,base_url='http://127.0.0.1:19265') as client:
        client.headers['X-App-Token']=app.state.token
        def post(route,data):
            r=client.post('/api/documents/'+route,json=data);r.raise_for_status();return r.json()
        def wait(ident):
            deadline=time.monotonic()+200
            while time.monotonic()<deadline:
                j=post('status',{'id':ident})
                if j['state'] in {'ready','error','cancelled'}:return j
                time.sleep(.1)
            raise TimeoutError('audit timed out')
        for source in (filename_case,simple_case):
            print('START',source.name,flush=True);before=sha(source)
            r=client.post('/api/documents/upload',params={'filename':source.name},content=source.read_bytes(),headers={'Content-Type':'application/octet-stream'});r.raise_for_status();ident=r.json()['id']
            try:
                j=wait(ident);row={'file':source.name,'state':j['state'],'candidates':j['candidates'],'manifest':j.get('manifest')}
                if j['state']=='ready' and not j['manifest']['blockers']:
                    post('export',{'id':ident,'revision':j['revision'],'choices':{c['id']:{'mode':'full'} for c in j['candidates']},'regions':[]});done=wait(ident)
                    row['exportError']=done.get('error')
                    if done.get('exportResult'):
                        r=client.get(f'/api/documents/{ident}/download');r.raise_for_status();out=here/(source.stem+'__reviewed.docx');out.write_bytes(r.content)
                        audit=external_audit(out,['김민수','010-0000-1234','sample@example.invalid'])
                        row.update(suggestedFilename=done['exportResult']['filename'],downloadContentDisposition=r.headers.get('content-disposition'),rescanCount=len(done['exportResult']['candidates']),independent={'remaining':audit['remaining']})
                row['originalUnchanged']=sha(source)==before;report.append(row)
                print(json.dumps({k:v for k,v in row.items() if k not in {'manifest','candidates'}},ensure_ascii=False),flush=True)
            finally:post('remove',{'id':ident})
    (here/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
