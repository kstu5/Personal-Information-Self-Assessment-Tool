"""Render the actual fixtures and saved copies for visual verification."""
from pathlib import Path
import json,os,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
RENDER=Path(os.environ.get('DOCX_RENDERER',str(Path.home()/'.codex/plugins/cache/openai-primary-runtime/documents/26.1022.11436/skills/documents/render_docx.py')))
RUNTIME=Path(os.environ.get('DOCUMENT_RUNTIME',str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies')))
PYTHON=RUNTIME/'python/python.exe'
POPPLER=RUNTIME/'native/poppler/Library/bin'
def main():
    env=os.environ.copy();env['PATH']=str(ROOT/'.runtime/file-tools/libreoffice/program')+os.pathsep+str(POPPLER)+os.pathsep+env['PATH']
    reports=[]
    sources=list((HERE/'fixtures').glob('*.docx'))+list((HERE/'reviewed').glob('*__auto_full.docx'))
    for p in sources:
        out=HERE/'qa'/('original_' if p.parent.name=='fixtures' else 'output_')/p.stem;out.mkdir(parents=True,exist_ok=True)
        result=subprocess.run([str(PYTHON),str(RENDER),str(p),'--output_dir',str(out),'--emit_pdf','--dpi','100'],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=100)
        record={'file':str(p.relative_to(HERE)),'exitCode':result.returncode,'pages':[str(x.relative_to(HERE)) for x in out.glob('page-*.png')],'log':result.stdout+result.stderr};reports.append(record)
        print(p.name,result.returncode,len(record['pages']),flush=True)
    import pymupdf as fitz
    for p in list((HERE/'fixtures').glob('*.pdf'))+list((HERE/'reviewed').glob('*__auto_full.pdf')):
        out=HERE/'qa'/('original_' if p.parent.name=='fixtures' else 'output_')/p.stem;out.mkdir(parents=True,exist_ok=True)
        with fitz.open(p) as d:
            for i,page in enumerate(d):page.get_pixmap(matrix=fitz.Matrix(1.25,1.25)).save(out/f'page-{i+1}.png')
        reports.append({'file':str(p.relative_to(HERE)),'exitCode':0,'pages':[str(x.relative_to(HERE)) for x in out.glob('page-*.png')]})
    (HERE/'results/rendering.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
