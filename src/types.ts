export type Draft = { title: string; body: string };
export type Risk = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
export type Candidate = {
  id: string; source: 'title' | 'body'; start: number; end: number;
  text: string; label: string; labelName: string; risk: Risk;
};
export type CheckResult = { candidates: Candidate[]; revision: number; engine: string; elapsedMs: number };
export type PostDocument = Draft & { format: 'before-post-document'; version: 1; savedAt: string };
export type FileHandle = {
  name: string;
  getFile(): Promise<File>;
  createWritable(): Promise<{ write(data: string): Promise<void>; close(): Promise<void>; abort(): Promise<void> }>;
};
export type SavedFile = { name: string; savedAt: string; fileId?: string; handle?: FileHandle; digest?: string };
declare global {
  interface Window {
    showSaveFilePicker?: (options: object) => Promise<FileHandle>;
    showOpenFilePicker?: (options: object) => Promise<FileHandle[]>;
    requestAppClose?: () => void;
  }
}
