import test from 'node:test';
import assert from 'node:assert/strict';
import {previewView,readingParts,contentPage} from '../src/filePreview.ts';

test('all twelve supported extensions have an appropriate default preview',()=>{
  for(const [kind,view] of Object.entries({'.txt':'content','.csv':'sheet','.tsv':'sheet','.docx':'pages','.pptx':'pages','.hwpx':'content','.hwp':'content','.xlsx':'sheet','.pdf':'images','.png':'images','.jpg':'images','.jpeg':'images'}))assert.equal(previewView(kind),view,kind);
  assert.equal(previewView('.unknown'),'text');
});

test('body ordering and selected content page are independent of metadata positions',()=>{
  const sections=[{id:'s10',flow:{section:'Contents/section10.xml',order:1}},{id:'metadata'},
    {id:'s2',flow:{section:'Contents/section2.xml',order:2}},{id:'s0',flow:{section:'Contents/section0.xml',order:4}}];
  assert.deepEqual(readingParts(sections).map(p=>p.id),['s0','s2','s10']);
  const lines=Array.from({length:35},(_,i)=>({id:`line-${i}`,flow:{line:i+1}}));
  assert.equal(contentPage([{id:'meta'},...lines],'line-32'),1);
  assert.equal(contentPage(lines,'missing'),0);
});
