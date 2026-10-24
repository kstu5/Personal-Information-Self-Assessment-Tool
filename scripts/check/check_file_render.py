"""Independent LibreOffice rendering of generated Office copies (test outputs only)."""
from pathlib import Path
import sys,subprocess,json,time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.runtime'/'file-python'))
import pymupdf as fitz

def main():
    source=ROOT/'output'/'file-feature-validation';out=source/('render-'+str(time.time_ns()));out.mkdir()
    profile=out/'profile';rows=[]
    for name in ('meeting-reviewed.docx','briefing-reviewed.pptx','participants-reviewed.xlsx'):
        folder=out/Path(name).stem;folder.mkdir()
        r=subprocess.run([str(ROOT/'.runtime'/'file-tools'/'libreoffice'/'program'/'soffice.com'),'-env:UserInstallation='+profile.as_uri(),'--headless','--norestore','--nodefault','--convert-to','pdf','--outdir',str(folder),str(source/name)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        pdf=folder/(Path(name).stem+'.pdf');assert not r.returncode and pdf.exists(),name
        with fitz.open(pdf) as d:
            for i,p in enumerate(d):p.get_pixmap(alpha=False).save(folder/f'page-{i+1}.png')
            rows.append({'file':name,'pages':len(d),'rendered':True,'folder':str(folder)})
        print(name,'rendered',flush=True)
    (source/'render-report.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
