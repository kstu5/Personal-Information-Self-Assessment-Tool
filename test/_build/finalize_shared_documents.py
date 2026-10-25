from pathlib import Path
import concurrent.futures,json,os,shutil,subprocess,sys,zipfile
from lxml import etree as E
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'test/shared-document-examples';QA=ROOT/'test/qa/shared-documents'
RUNTIME=Path(os.environ.get('DOCUMENT_RUNTIME',str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies')))
PYTHON=RUNTIME/'python/python.exe'
POPPLER=RUNTIME/'native/poppler/Library/bin'
RENDER=Path(os.environ.get('DOCX_RENDERER',str(Path.home()/'.codex/plugins/cache/openai-primary-runtime/documents/26.1022.11436/skills/documents/render_docx.py')))
def render(path):
    env=os.environ.copy();env['PYTHONUTF8']='1';env['PATH']=str(ROOT/'.runtime/file-tools/libreoffice/program')+os.pathsep+str(POPPLER)+os.pathsep+env['PATH']
    out=QA/path.stem;out.mkdir(exist_ok=True)
    r=subprocess.run([str(PYTHON),'-X','utf8',str(RENDER),str(path),'--output_dir',str(out),'--emit_pdf','--dpi','110'],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
    pages=sorted(out.glob('page-*.png'));record={'file':path.name,'returnCode':r.returncode,'pages':[str(p.relative_to(ROOT)) for p in pages],'log':r.stdout+r.stderr}
    if r.returncode or not pages:raise RuntimeError(record)
    print(path.name,'pages',len(pages),flush=True)
    return record
def main():
    QA.mkdir(parents=True,exist_ok=True)
    workbook=OUT/'추첨당첨자_명단예시.xlsx'
    with zipfile.ZipFile(workbook) as z:entries={n:z.read(n) for n in z.namelist()}
    tree=E.fromstring(entries['xl/workbook.xml']);sheets=[e for e in tree.iter() if E.QName(e).localname=='sheet'];assert sheets[1].get('name')=='내부_배송정보';sheets[1].set('state','hidden');entries['xl/workbook.xml']=E.tostring(tree,xml_declaration=True,encoding='UTF-8')
    with zipfile.ZipFile(workbook,'w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in entries.items():z.writestr(name,raw)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:records=list(pool.map(render,sorted(OUT.glob('*.docx'))))
    (QA/'rendering.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    for name in ('이력서_검사예시','행사참가자_안내예시'):
        shutil.copy2(QA/name/(name+'.pdf'),OUT/(name+'.pdf'))
    subprocess.run([str(PYTHON),'-X','utf8',str(ROOT/'test/_build/create_shared_documents.py'),'answers'],check=True)
    readme='''# 공유 문서 검사 예시 모음

모든 인적사항과 기관은 가상 예시입니다. 앱의 파일 검사에서 파일을 하나씩 열어 사용하세요.

| 파일 | 확인할 상황 |
|---|---|
| 이력서_검사예시.docx | 기본 인적사항, 추천인 정보, 반복 연락처, 본문과 표 |
| 이력서_검사예시.pdf | 같은 이력서의 검색 가능한 PDF 글자층과 페이지 검사 |
| 추첨당첨자_명단예시.xlsx | 당첨자 10명의 명단과 숨김 시트인 내부_배송정보의 연락처·이메일·주소 |
| 행사참가자_안내예시.docx | 참가자 8명의 명단, 행사 장소, 진행 담당자 연락처 |
| 행사참가자_안내예시.pdf | 같은 참가자 안내문의 PDF 검사 |
| 회의록_공유예시.docx | 참석자·후속 연락처와 Word 메모·메모 작성자·문서 작성자 |
| 배송요청서_공유예시.docx | 수취인 5명의 이름·전화·주소와 담당자 연락처 |

검사_확인목록.md와 확인목록.json은 정답 비교용입니다. 검사 입력에 함께 넣지 마세요.
PDF는 이미지로만 만든 스캔본이 아닙니다. 같은 내용을 서로 다른 형식으로 비교할 수 있습니다.
개인정보 후보의 단순 건수보다 해당 값이 정확한 위치에서 잡히는지, 선택한 가림이 실제 사본에 반영되는지 확인하세요.
학교·회사·직책 같은 문맥 정보와 오탐 여부도 별도로 확인하세요. 이 모음은 일반적인 정확도 보장용 표본이 아닙니다.
'''
    (OUT/'사용안내.md').write_text(readme,encoding='utf-8')
    for p in OUT.glob('*.inspect.ndjson'):p.replace(QA/p.name)
    deliver=[p for p in sorted(OUT.iterdir()) if p.suffix in {'.docx','.pdf','.xlsx','.md','.json'}]
    with zipfile.ZipFile(OUT/'공유문서_검사예시_모음.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in deliver:z.write(p,p.name)
    print('Packaged',len(deliver),'files',flush=True)
if __name__=='__main__':main()
