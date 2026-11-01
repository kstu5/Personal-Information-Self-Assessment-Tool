"""An actual second model pass over source-bound candidate contexts.

Only original excerpts/field labels enter inference. Review never generates
replacement text, persists file vocabulary, or suppresses validated numbers.
"""
from dataclasses import replace
import re
from backend.candidate_context import assess_candidates,_person_field
from backend.detection_context import date_field_role

CONTEXT_TYPES=frozenset({'PERSON','ADDRESS','DT_BIRTH'})
_ORG_END=re.compile(r'(?:회사|은행|뱅크|센터|연구소|재단|협회|대학교|병원|공단|공사|Inc\.?|Ltd\.?)$',re.I)


def _window(text,d,scopes):
    scope=next((s for s in scopes or () if s['start']<=d.start<d.end<=s['end']),None)
    if scope is None:
        a=text.rfind('\n',0,d.start)+1;b=text.find('\n',d.end)
        b=len(text) if b<0 else b
        scope={'start':a,'end':b}
        # A short, complete label on the preceding line belongs in the reread.
        # Do not infer a header from a previous person's value or old sentence.
        from backend.file_context import field_role
        previous=text[:a].rstrip().rsplit('\n',1)[-1].strip()
        if previous and len(previous)<=80 and (field_role(previous) or date_field_role(previous)):
            scope['prefix']=previous
    a,b=scope['start'],scope['end']
    # Share short contexts and align longer ones on stable bins. Every target
    # remains complete; overflow windows in the tokenizer preserve long spans.
    lo=max(a,((d.start-a)//256)*256+a-128)
    hi=min(b,max(lo+640,d.end+96))
    prefix=scope.get('prefix','')[-384:]
    suffix=scope.get('suffix','')[:192]
    if prefix:prefix+='\n'
    joined=bool(scope.get('joinSuffix') and d.end==b and len(d.text)==1
                and re.fullmatch('[가-힣]',d.text) and not _person_field(text,d.start,d.end))
    if suffix and not joined:suffix='\n'+suffix
    scope={**scope,'joinedWord':joined}
    value=prefix+text[lo:hi]+suffix
    start=len(prefix)+d.start-lo;end=start+(d.end-d.start)
    assert value[start:end]==d.text
    return value,start,end,scope


def review_candidates(text,detections,analyze_many,scopes=None):
    inputs=[];indices={};plans=[]
    for d in detections:
        if not 0<=d.start<d.end<=len(text) or text[d.start:d.end]!=d.text:
            raise ValueError('Invalid secondary target')
        if d.label not in CONTEXT_TYPES:continue
        value,start,end,scope=_window(text,d,scopes)
        if value not in indices:indices[value]=len(inputs);inputs.append(value)
        plans.append((d,indices[value],start,end,scope))
    readings=analyze_many(inputs) if inputs else []
    if len(readings)!=len(inputs):raise ValueError('Missing secondary result')
    reviewed={}
    for d,index,start,end,scope in plans:
        source=inputs[index];reading=readings[index]
        # Even a model returning nothing has completed the second pass. Absence
        # of a tag is not proof that a private value is safe to discard.
        local=replace(d,start=start,end=end)
        for vote in reading:
            if not 0<=vote.start<vote.end<=len(source) or source[vote.start:vote.end]!=vote.text:
                raise ValueError('Invalid secondary model offsets')
        person=any(a<=d.start<d.end<=b for a,b in scope.get('personRanges',())) or _person_field(source,start,end)
        if d.label=='PERSON' and scope.get('joinedWord') and not person:
            word=re.match('[가-힣]+',source[start:])
            if word and len(word[0])>1 and not any(v.label=='PERSON' and v.start<start+len(word[0]) and start<v.end for v in reading):
                reviewed[id(d)]=None;continue
        date_role=date_field_role(scope.get('dateLabel'))
        if d.label=='DT_BIRTH' and date_role=='schedule':
            from backend.detection_context import schedule_date_field
            if schedule_date_field(d.text,scope['dateLabel']):
                reviewed[id(d)]=None;continue
        if d.label=='PERSON' and not person and any(v.label=='ORGANIZATION' and
                v.start<=start<end<=v.end and _ORG_END.search(v.text) for v in reading):
            reviewed[id(d)]=None;continue
        from backend.nonpersonal_context import filter_nonpersonal
        assessed=assess_candidates(source,filter_nonpersonal(source,[local]),reading)
        match=next((v for v in assessed if v.start==start and v.end==end and v.label==d.label),None)
        # Original schema fields outrank an unrelated name/date vote from a row.
        protected=person and d.label=='PERSON' or date_role=='birth' and d.label=='DT_BIRTH'
        if match is None and not protected:
            reviewed[id(d)]=None;continue
        supported=protected or match is not None and match.extra.get('contextReview',{}).get('state')=='supported'
        reason=('문서 항목과 주변 문맥을 재검토해 개인정보 후보로 유지했습니다.' if supported else
                '주변 문맥을 다시 분석했으며 개인정보 가능성이 있어 후보로 유지했습니다.')
        reviewed[id(d)]=replace(d,extra={**(d.extra or {}),'contextReview':{
            'state':'supported' if supported else 'uncertain','secondary':True,
            'decision':'retain','reason':reason}})
    return [reviewed.get(id(d),d) for d in detections if reviewed.get(id(d),d) is not None]


class FileReviewContexts:
    """Original table/header excerpts for a single file, never across files."""
    def __init__(self,parts,context,date_fields):
        from backend.file_context import _table_position,field_role
        self.parts=parts;self.context=context;self.date_fields=date_fields
        self.positions={};self.rows={};self.headers={}
        self.pdf_lines={}
        self.pdf_continuations={}
        for p in parts:
            c=p.get('pdfContext',{});target=p.get('target',{})
            if target.get('kind')=='pdftext' and c.get('horizontal') and not p.get('textLayerUncertain'):
                key=(p.get('asset'),target.get('page'),c.get('block'),c.get('line'))
                self.pdf_lines[key]=p
            position=_table_position(p)
            if position:
                table,row,col,span=position
                if not isinstance(row,int) or not isinstance(col,int):continue
                self.positions[p['id']]=(table,row,col)
                self.rows.setdefault((table,row),[]).append((col,p))
        # Some PDF producers put each wrapped line in a separate text block.
        # Link only aligned, same-size native lines when the upper line reaches
        # the page's text edge; never cross pages or uncertain/rotated layers.
        def bounds(p):
            bs=p.get('boxes',[])
            return (min(b[0] for b in bs),min(b[1] for b in bs),max(b[2] for b in bs),max(b[3] for b in bs)) if bs else None
        right={}
        for p in self.pdf_lines.values():
            box=bounds(p)
            if box:right[p.get('asset')]=max(right.get(p.get('asset'),0),box[2])
        for p,q in zip(parts,parts[1:]):
            a,b=p.get('pdfContext',{}),q.get('pdfContext',{})
            if not a.get('horizontal') or not b.get('horizontal') or p.get('textLayerUncertain') or q.get('textLayerUncertain'):continue
            if p.get('asset')!=q.get('asset') or p.get('target',{}).get('page')!=q.get('target',{}).get('page'):continue
            if not isinstance(a.get('block'),int) or b.get('block')!=a['block']+1 or b.get('line')!=0:continue
            x,y=bounds(p),bounds(q)
            if not x or not y:continue
            h=x[3]-x[1];k=y[3]-y[1]
            if h>0 and abs(h-k)<=h*.15 and abs(x[0]-y[0])<=h*.25 and .9*h<=y[1]-x[1]<=1.6*h and x[2]>=right.get(p.get('asset'),x[2])-h*.5:
                self.pdf_continuations[p['id']]=q
        for (table,row),items in self.rows.items():
            ordered=sorted(items,key=lambda x:x[0])
            if all(field_role(p['text']) or date_field_role(p['text']) for _,p in ordered):
                self.headers.setdefault(table,[]).append((row,' | '.join(p['text'] for _,p in ordered)))
        for table in self.headers:self.headers[table].sort()

    def scopes(self,offsets):
        from backend.file_review import utf16
        result=[]
        for start,end,p in offsets:
            s={'start':start,'end':end}
            s['personRanges']=[(start+utf16(p['text'][:f.start]),start+utf16(p['text'][:f.end]))
                               for f in self.context.fields[p['id']] if f.role=='person']
            label=self.date_fields.get(p['id']) or self.context.pdf_labels.get(p['id'])
            if label:s['prefix']=label;s['dateLabel']=label
            c=p.get('pdfContext',{});target=p.get('target',{})
            if target.get('kind')=='pdftext' and c.get('horizontal') and not p.get('textLayerUncertain') and isinstance(c.get('line'),int):
                following=self.pdf_lines.get((p.get('asset'),target.get('page'),c.get('block'),c['line']+1)) or self.pdf_continuations.get(p['id'])
                if following and len(p['text'])>=20 and re.search(r' [가-힣]$',p['text']) and re.match('[가-힣]',following['text']):
                    from backend.file_context import field_role
                    next_label=following['text'].split(':',1)[0].split('：',1)[0]
                    if not field_role(next_label):
                        s['suffix']=following['text'];s['joinSuffix']=True
            position=self.positions.get(p['id'])
            if position:
                table,row,col=position
                items=sorted(self.rows[(table,row)],key=lambda x:x[0])
                before=[];after=[];seen=False
                for _,item in items:
                    if item['id']==p['id']:seen=True;continue
                    (after if seen else before).append(item['text'])
                headings=[value for r,value in self.headers.get(table,()) if r<row]
                prefix=((headings[-1]+'\n') if headings else '')+' | '.join(before)
                if label:prefix=prefix+'\n'+label
                s['prefix']=prefix;s['suffix']=' | '.join(after)
            result.append(s)
        return result
