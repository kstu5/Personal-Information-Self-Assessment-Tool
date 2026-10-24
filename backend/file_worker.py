"""Isolated adapter process: bounded lifetime, no Python network, private output."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    def deny_network(event,args):
        if event in {'socket.connect','socket.getaddrinfo','socket.sendto'}:
            raise RuntimeError('Document processing is offline')
    sys.addaudithook(deny_network)
    from backend.file_formats import Document, FormatError
    job=Path(sys.argv[1]); spec=json.loads(job.read_text(encoding='utf-8'))
    work=job.parent; response=work/spec['response']
    try:
        doc=Document(work/spec['source'],work).load()
        if spec['action']=='export':
            output=work/spec['output']
            doc.export(output,spec['edits'],spec['regions'])
            verified=work/'verification';verified.mkdir(exist_ok=True)
            reread=Document(output,verified).load()
            # For editable text sources, re-extraction must contain the exact expected text at the same target.
            by_target={json.dumps(p['target'],sort_keys=True):p['text'] for p in reread.parts}
            for p in doc.parts:
                if p['id'] not in spec['edits']: continue
                want=spec['edits'][p['id']]
                got=by_target.get(json.dumps(p['target'],sort_keys=True),'')
                # Empty strings are intentionally omitted by the extractor.
                if got!=want and not(not got and not want.strip()) and not(doc.kind in {'.csv','.tsv'} and got=="'"+want):
                    raise FormatError('저장한 사본의 수정 위치를 재확인하지 못했습니다. 파일을 제공하지 않습니다.')
            manifest=reread.manifest()
        else:
            manifest=doc.manifest()
        response.write_text(json.dumps({'ok':True,'manifest':manifest},ensure_ascii=False),encoding='utf-8')
    except FormatError as e:
        response.write_text(json.dumps({'ok':False,'message':str(e)},ensure_ascii=False),encoding='utf-8')
    except Exception:
        # Never include source text, filenames embedded in third-party exceptions, or tracebacks.
        response.write_text(json.dumps({'ok':False,'message':'문서를 읽거나 사본을 검증하지 못했습니다. 손상·암호화·미지원 구조 또는 읽기 도구 설치 상태를 확인해 주세요.'},ensure_ascii=False),encoding='utf-8')

if __name__=='__main__': main()
