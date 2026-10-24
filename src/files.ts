import { api, boot } from './api';
import type { Draft, PostDocument, SavedFile, FileHandle } from './types';

export function filenameFromTitle(title: string): string {
  let name = title.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '').replace(/\s+/g, ' ').trim().replace(/[. ]+$/g, '');
  name = Array.from(name).reduce((value, char) => value.length + char.length <= 120 ? value + char : value, '');
  name = name.replace(/[. ]+$/g, '') || '제목 없음';
  if (/^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])$/i.test(name.split('.')[0])) name = '_' + name;
  return name;
}

export function validateDocument(value: unknown): PostDocument {
  const d = value as Partial<PostDocument> | null;
  if (!d || typeof d !== 'object' || d.format !== 'before-post-document') throw new Error('이 프로그램에서 저장한 작업 파일을 선택해 주세요.');
  if (d.version !== 1) throw new Error('지원하지 않는 작업 파일 버전입니다.');
  if (typeof d.title !== 'string' || typeof d.body !== 'string' || typeof d.savedAt !== 'string' || Number.isNaN(Date.parse(d.savedAt))) throw new Error('작업 파일의 내용을 읽을 수 없습니다.');
  if (Array.from(d.title).length > boot.maxTitle || Array.from(d.body).length > boot.maxBody) throw new Error('제목은 300자, 본문은 30,000자까지 사용할 수 있습니다.');
  return { format: 'before-post-document', version: 1, title: d.title, body: d.body, savedAt: d.savedAt };
}

async function digest(file: File): Promise<string> {
  if (file.size > 2_000_000) throw new Error('파일이 너무 큽니다. 2 MB 이하의 작업 파일을 선택해 주세요.');
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))).map(x => x.toString(16).padStart(2,'0')).join('');
}
const types = [{ description: '게시 전 작업 파일', accept: { 'application/json': ['.piipost'] } }];
export function cancelled(error: unknown): boolean { return error instanceof DOMException && error.name === 'AbortError'; }

export async function openDocument(): Promise<{ draft: Draft; file: SavedFile } | null> {
  if (boot.desktop) {
    const result = await api<{ cancelled?: boolean; fileId: string; name: string; document: PostDocument }>('files/open', {});
    if (result.cancelled) return null;
    const d = validateDocument(result.document);
    return { draft: {title:d.title, body:d.body}, file: {fileId:result.fileId, name:result.name, savedAt:d.savedAt} };
  }
  if (!window.showOpenFilePicker) throw new Error('이 브라우저는 파일 위치 선택을 지원하지 않습니다. Windows 프로그램 창이나 최신 Edge에서 열어 주세요.');
  const [handle] = await window.showOpenFilePicker({types, multiple:false});
  const file = await handle.getFile();
  const hash = await digest(file);
  let parsed: unknown;
  try { parsed = JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(await file.arrayBuffer())); }
  catch { throw new Error('작업 파일을 읽을 수 없습니다. 파일이 손상되었거나 다른 형식입니다.'); }
  const d = validateDocument(parsed);
  return {draft:{title:d.title, body:d.body}, file:{name:handle.name, savedAt:d.savedAt, handle, digest:hash}};
}

export async function saveDocument(draft: Draft, current: SavedFile | null, asNew: boolean, suggestion: string): Promise<SavedFile | null> {
  if (boot.desktop) {
    const result = await api<SavedFile & {cancelled?:boolean}>('files/save', {...draft, fileId:current?.fileId || null, saveAs:asNew, filename:filenameFromTitle(suggestion)});
    return result.cancelled ? null : result;
  }
  if (!window.showSaveFilePicker) throw new Error('이 브라우저는 저장 위치 선택을 지원하지 않습니다. Windows 프로그램 창이나 최신 Edge에서 열어 주세요.');
  let handle: FileHandle;
  if (!asNew && current?.handle) {
    handle = current.handle;
    let file: File;
    try { file = await handle.getFile(); }
    catch { throw new Error('기존 파일에 접근할 수 없습니다. 다른 이름으로 저장해 주세요.'); }
    if (await digest(file) !== current.digest) throw new Error('파일이 프로그램 밖에서 변경되었습니다. 다른 이름으로 저장해 주세요.');
  } else {
    handle = await window.showSaveFilePicker({suggestedName:filenameFromTitle(suggestion)+'.piipost', types, excludeAcceptAllOption:true});
  }
  const document: PostDocument = {...draft, format:'before-post-document', version:1, savedAt:new Date().toISOString()};
  const data = JSON.stringify(document, null, 2);
  const writable = await handle.createWritable();
  try { await writable.write(data); await writable.close(); }
  catch { try {await writable.abort();} catch { /* best effort; preserve the current draft */ } throw new Error('저장하지 못했습니다. 권한·저장 공간·장치 연결을 확인해 주세요.'); }
  return {name:handle.name, handle, savedAt:document.savedAt, digest:await digest(new File([data],handle.name))};
}
