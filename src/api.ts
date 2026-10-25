export const boot: {token: string; desktop: boolean; maxTitle: number; maxBody: number; model?:string} = JSON.parse(
  document.querySelector('meta[name="app-boot"]')?.getAttribute('content') ||
  '{"token":"","desktop":false,"maxTitle":300,"maxBody":30000}',
);

export async function api<T>(path: string, data: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/${path}`, { method: 'POST', cache: 'no-store', signal,
      headers: { 'Content-Type': 'application/json', 'X-App-Token': boot.token }, body: JSON.stringify(data) });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e;
    throw new Error('로컬 검사 기능에 연결하지 못했습니다. 프로그램이 실행 중인지 확인해 주세요.');
  }
  let result;
  try { result = await response.json(); }
  catch { throw new Error('응답을 읽지 못했습니다. 글은 그대로 유지됩니다.'); }
  if (!response.ok) throw new Error(result.message || '작업을 완료하지 못했습니다. 다시 시도해 주세요.');
  return result;
}
