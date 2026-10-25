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
    from backend.file_formats import Document, FormatError, verify_text_edits
    job=Path(sys.argv[1]); spec=json.loads(job.read_text(encoding='utf-8'))
    work=job.parent; response=work/spec['response']
    try:
        doc=Document(work/spec['source'],work).load()
        if spec['action']=='export':
            output=work/spec['output']
            doc.export(output,spec['edits'],spec['regions'])
            verified=work/'verification';verified.mkdir(exist_ok=True)
            reread=Document(output,verified).load()
            verify_text_edits(doc,reread,spec['edits'])
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
