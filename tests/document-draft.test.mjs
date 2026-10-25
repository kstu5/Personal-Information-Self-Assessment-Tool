import test from 'node:test';
import assert from 'node:assert/strict';
import {draftChunks,draftStatus,fileReplacement} from '../src/documentDraft.ts';
import {EMPTY_SELECTION} from '../src/documentTypes.ts';

const part={id:'p1',text:'😀 김민수 / 김민수 / minsu@example.invalid'};
const make=(text,from=0,label='PERSON')=>{
  const start=part.text.indexOf(text,from);
  return {id:`c${start}`,part:part.id,text,start,end:start+text.length,label,labelName:label,source:'body',risk:'HIGH',location:'가상 문단'};
};
const first=make('김민수'),second=make('김민수',first.end),email=make('minsu@example.invalid',0,'EMAIL');
const value=(s,applied,candidates=[email,second,first])=>draftChunks(part,candidates,s,applied).map(c=>c.text).join('');

test('original/applied toggle retains source and changes only assigned occurrences, including UTF-16 offsets',()=>{
  const state={...EMPTY_SELECTION,choices:{[first.id]:{mode:'partial'},[email.id]:{mode:'custom',text:'공개 창구'}}};
  assert.equal(value(state,false),part.text);
  assert.equal(value(state,true),'😀 김** / 김민수 / 공개 창구');
  assert.equal(value(state,false),part.text);
  assert.equal(part.text,'😀 김민수 / 김민수 / minsu@example.invalid');
});

test('unassigned, explicitly kept, and canceled choices remain distinct',()=>{
  const state={...EMPTY_SELECTION,choices:{}};
  assert.equal(draftStatus(first,state),'unset');
  state.choices[first.id]={mode:'keep'};
  assert.equal(draftStatus(first,state),'keep');
  assert.equal(value(state,true),part.text);
  delete state.choices[first.id];
  assert.equal(draftStatus(first,state),'unset');
});

test('whole-part edit including empty content takes precedence only in applied view',()=>{
  const state={...EMPTY_SELECTION,textEdits:{[part.id]:''},choices:{[first.id]:{mode:'full'}}};
  assert.equal(value(state,true),'');
  assert.equal(value(state,false),part.text);
  assert.equal(draftStatus(first,state),'text');
});

test('preview uses server partial value and safely retains literal custom and empty replacements',()=>{
  assert.equal(fileReplacement({...first,partialText:'김○○'},{mode:'partial'}),'김○○');
  const state={...EMPTY_SELECTION,choices:{[first.id]:{mode:'full'},[second.id]:{mode:'custom',text:'<문의> & 안내'},[email.id]:{mode:'custom',text:''}}};
  assert.equal(value(state,true),'😀 █████ / <문의> & 안내 / ');
  assert.equal(draftStatus(email,state),'custom');
});
