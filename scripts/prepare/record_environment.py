from pathlib import Path
import importlib.metadata as metadata
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
(ROOT/'runtime.local.json').write_text(json.dumps({'python':sys.executable},indent=2),encoding='utf-8')
packages=sorted(metadata.distributions(path=[str(ROOT/'.runtime/python')]),key=lambda d:d.metadata['Name'].lower())
(ROOT/'requirements.lock.txt').write_text('# Verified Windows Python 3.12 environment including test dependencies\n'+'\n'.join(d.metadata['Name']+'=='+d.version for d in packages)+'\n',encoding='utf-8')
(ROOT/'docs').mkdir(exist_ok=True)
lines=['# Third party dependencies','','Recorded 2026-10-16. Review full license terms before redistributing a packaged executable.','','| Package | Version | License metadata |','|---|---|---|']
lines += ['| '+d.metadata['Name']+' | '+d.version+' | '+(d.metadata.get('License-Expression') or d.metadata.get('License') or 'See distribution license').splitlines()[0].replace('|','/')+' |' for d in packages]
lines += ['', 'Frontend versions are pinned in package.json and pnpm-lock.yaml. React and React DOM use MIT; Vite uses MIT; TypeScript uses Apache-2.0. Keep their accompanying distribution notices when packaging.']
(ROOT/'docs/DEPENDENCIES.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
script='''Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " & Chr(34) & root & "\\scripts\\start.ps1" & Chr(34)
shell.Run command, 0, False
'''
(ROOT/'게시전 실행.vbs').write_text(script,encoding='utf-16')
# Windows PowerShell 5.1 needs a BOM for the Korean error messages.
for name in ['start.ps1','setup.ps1']:
    path=ROOT/'scripts'/name
    source=path.read_text(encoding='utf-8-sig')
    path.write_text(source,encoding='utf-8-sig')
print('Runtime settings, locked dependencies, notices and launcher written.')
