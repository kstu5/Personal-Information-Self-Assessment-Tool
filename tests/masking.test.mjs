import test from 'node:test';
import assert from 'node:assert/strict';
import {partialMask,replacement,maskedDraft,validateCandidates} from '../src/masking.ts';

const make=(draft,source,text,from=0,label='PERSON')=>{
  const start=draft[source].indexOf(text,from);
  return {id:`${source}-${start}`,source,start,end:start+text.length,text,label,labelName:label,risk:'HIGH'};
};
test('partial masks preserve useful context but hide the sensitive segment',()=>{
  const cases=[
    ['PERSON','김하늘','김**'],['PERSON','박','*'],['PERSON','e\u0301하늘','e\u0301**'],
    ['PHONE','010-1234-5678','010-****-5678'],['PHONE','02-123-4567','02-***-4567'],
    ['PHONE','1588-1234','****-1234'],['EMAIL','a@example.com','*@example.com'],
    ['EMAIL','haneul@example.com','h*****@example.com'],
    ['RRN','990101-1000000','990101-*******'],['CARD','1234-5678-9012-3456','****-****-****-3456'],
    ['ADDRESS','서울특별시 마포구 예시로 12, 302호','서울특별시 ***'],
  ];
  for(const [label,text,expected] of cases)assert.equal(partialMask({label,text}),expected);
});
test('full mask has fixed length and keep/absent choices return the original',()=>{
  for(const text of ['김','김하늘','😀 긴 주소']){
    const candidate={text,label:'PERSON'};
    assert.equal(replacement(candidate,{mode:'full'}),'█████');
    assert.equal(replacement(candidate,{mode:'keep'}),text);
    assert.equal(replacement(candidate),text);
  }
});
test('offset-based replacement separates repeats, fields and Unicode; cancel restores just one occurrence',()=>{
  const draft={title:'김하늘 공지',body:'😀 e\u0301 김하늘\n\n다음 김하늘에게 문의하세요.'};
  const first=make(draft,'body','김하늘'), second=make(draft,'body','김하늘',first.end), title=make(draft,'title','김하늘');
  const candidates=[second,title,first];
  validateCandidates(draft,candidates);
  const choices={[title.id]:{mode:'full'},[first.id]:{mode:'partial'},[second.id]:{mode:'custom',text:'운영팀 <문의> & 쪽지'}};
  assert.deepEqual(maskedDraft(draft,candidates,choices),{
    title:'█████ 공지',body:'😀 e\u0301 김**\n\n다음 운영팀 <문의> & 쪽지에게 문의하세요.',
  });
  delete choices[first.id];
  assert.equal(maskedDraft(draft,candidates,choices).body,'😀 e\u0301 김하늘\n\n다음 운영팀 <문의> & 쪽지에게 문의하세요.');
  assert.equal(draft.title,'김하늘 공지');
});
test('replacement never changes matching text outside detected offsets',()=>{
  const draft={title:'',body:'박하차와 박하, 그리고 박하차'};
  const c=make(draft,'body','박하',4);
  assert.equal(maskedDraft(draft,[c],{[c.id]:{mode:'full'}}).body,'박하차와 █████, 그리고 박하차');
});
test('bad, stale, duplicated and overlapping offsets cannot open an editing session',()=>{
  const draft={title:'이름',body:'김하늘'},c=make(draft,'body','김하늘');
  for(const list of [[{...c,text:'박서윤'}],[{...c,start:-1}],[{...c,end:9}],[c,c],[c,{...c,id:'overlap',start:1,text:'하늘'}],[{...c,source:'unknown'}]]){
    assert.throws(()=>validateCandidates(draft,list));
  }
  assert.doesNotThrow(()=>validateCandidates(draft,[]));
});
