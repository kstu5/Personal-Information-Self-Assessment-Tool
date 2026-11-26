"""Bounded HWP 5 record edits with fresh compound-file serialization.

Unchanged records (tables, objects, fonts, paragraph styles) retain their bytes.
Editable spans end at structural control markers; browser positions never name
streams. Character shapes are carried with unchanged characters and inherited
by replacements. Changed paragraphs discard only their derived line cache.
"""
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import io
import re
import struct
import subprocess
import zlib

from backend.file_formats import FormatError

MAX_EXPANDED=80*1024*1024
EXTENDED={1,2,3,4,5,6,7,8,9,11,12,14,15,16,17,18,19,20,21,22,23}
REMOVED_ROOTS={'PrvText','PrvImage','DocHistory','Scripts','XMLTemplate','DocOptions','Signature','Signatures'}
REMOVED_ROOTS={name.casefold() for name in REMOVED_ROOTS}


def inflate(raw):
    obj=zlib.decompressobj(-15)
    try:value=obj.decompress(raw,MAX_EXPANDED+1)
    except zlib.error:raise FormatError('HWP 압축 기록이 손상되었습니다.')
    trailer=obj.unused_data
    # hwplib 1.1.11 writes a raw-deflate stream with its eight-byte gzip
    # trailer retained (zero CRC + original length). Other tails are rejected.
    valid_tail=not trailer or len(trailer)==8 and trailer[:4]==bytes(4) and struct.unpack('<I',trailer[4:])[0]==len(value)
    if len(value)>MAX_EXPANDED or obj.unconsumed_tail or not obj.eof or not valid_tail:
        raise FormatError('HWP 내부 압축 크기 또는 구조가 올바르지 않습니다.')
    return value


def deflate(raw):
    obj=zlib.compressobj(wbits=-15)
    return obj.compress(raw)+obj.flush()


@dataclass
class Record:
    tag:int
    level:int
    data:bytes


def records(raw):
    result=[];at=0
    while at<len(raw):
        if at+4>len(raw):raise FormatError('HWP 기록 헤더가 잘렸습니다.')
        head=struct.unpack_from('<I',raw,at)[0];at+=4
        tag,level,size=head&1023,(head>>10)&1023,head>>20
        if size==4095:
            if at+4>len(raw):raise FormatError('HWP 확장 기록이 잘렸습니다.')
            size=struct.unpack_from('<I',raw,at)[0];at+=4
        if at+size>len(raw) or len(result)>=100000 or level>128:raise FormatError('HWP 기록 크기·깊이·개수가 올바르지 않습니다.')
        result.append(Record(tag,level,raw[at:at+size]));at+=size
    return result


def record_bytes(items):
    out=bytearray()
    for item in items:
        size=len(item.data);out+=struct.pack('<I',item.tag|(item.level<<10)|(min(size,4095)<<20))
        if size>=4095:out+=struct.pack('<I',size)
        out+=item.data
    return bytes(out)


def package_read(raw):
    source=io.BytesIO(raw)
    def take(n):
        b=source.read(n)
        if len(b)!=n:raise FormatError('HWP 스트림 전송이 잘렸습니다.')
        return b
    def number():return struct.unpack('>I',take(4))[0]
    if take(8)!=b'HWPSTRM1':raise FormatError('HWP 스트림 형식이 올바르지 않습니다.')
    count=number();result={};directories={};total=0
    if not 1<=count<=4000:raise FormatError('HWP 내부 항목 수를 확인할 수 없습니다.')
    for _ in range(count):
        kind=take(1)[0];length=number()
        if length>4096:raise FormatError('HWP 내부 이름이 너무 깁니다.')
        name=take(length).decode('utf-8');size=number();total+=size
        if total>MAX_EXPANDED or name in result or name in directories:raise FormatError('HWP 내부 크기·이름이 올바르지 않습니다.')
        if name.startswith('/') or '\\' in name or any(v in {'.','..'} for v in name.split('/')):raise FormatError('HWP 내부 경로가 올바르지 않습니다.')
        data=take(size)
        if kind==0 and size==16:directories[name]=data
        elif kind==1 and name:result[name]=data
        else:raise FormatError('HWP 내부 항목이 올바르지 않습니다.')
    if source.read(1):raise FormatError('HWP 스트림 뒤에 예상하지 못한 내용이 있습니다.')
    return result,directories


def package_write(streams,directories):
    entries=[(0,k,v) for k,v in sorted(directories.items(),key=lambda pair:(pair[0].count('/'),len(pair[0]),pair[0]))]
    entries += [(1,k,v) for k,v in streams.items()]
    out=bytearray(b'HWPSTRM1'+struct.pack('>I',len(entries)))
    for kind,path,data in entries:
        name=path.encode('utf-8');out+=bytes([kind])+struct.pack('>I',len(name))+name+struct.pack('>I',len(data))+data
    return bytes(out)


@dataclass
class Token:
    raw:bytes
    text:str|None
    start:int
    style:int=0


def tokens(raw,styles):
    if len(raw)%2:raise FormatError('HWP 글자 기록 길이가 올바르지 않습니다.')
    result=[];at=0;style_at=0
    while at<len(raw):
        start=at//2;code=struct.unpack_from('<H',raw,at)[0]
        while style_at+1<len(styles) and styles[style_at+1][0]<=start:style_at+=1
        style=styles[style_at][1] if styles else 0
        width=16 if code in EXTENDED else 2
        if at+width>len(raw):raise FormatError('HWP 제어 문자가 잘렸습니다.')
        chunk=raw[at:at+width]
        if width==16 and struct.unpack_from('<H',chunk,14)[0]!=code:raise FormatError('HWP 제어 문자 경계가 올바르지 않습니다.')
        if code>=32:
            if 0xd800<=code<=0xdbff:
                if at+4>len(raw):raise FormatError('HWP 유니코드 글자가 잘렸습니다.')
                chunk=raw[at:at+4];width=4
            try:text=chunk.decode('utf-16-le')
            except UnicodeError:raise FormatError('HWP 유니코드 글자 위치가 올바르지 않습니다.')
        else:text={9:'\t',10:'\n',24:'-',30:'\u00a0',31:' '}.get(code)
        result.append(Token(chunk,text,start,style));at+=width
    return result


def new_token(char,style):
    if char=='\t':raw=struct.pack('<H',9)+bytes(12)+struct.pack('<H',9)
    elif char=='\n':raw=struct.pack('<H',10)
    elif ord(char)<32 or 0xd800<=ord(char)<=0xdfff:raise FormatError('HWP 수정 문구에 지원하지 않는 제어 문자가 있습니다.')
    else:raw=char.encode('utf-16-le')
    return Token(raw,char,0,style)


def changed_tokens(old,new):
    original=''.join(t.text for t in old);result=[];changes=[]
    old_offsets=[t.start for t in old]+[old[-1].start+len(old[-1].raw)//2 if old else 0]
    for tag,a,b,c,d in SequenceMatcher(None,original,new,autojunk=False).get_opcodes():
        if tag=='equal':result.extend(old[a:b])
        else:
            replacement=[]
            for index,char in enumerate(new[c:d]):
                source_index=min(a+index,b-1) if b>a else min(a,len(old)-1)
                style=old[source_index].style if old else 0
                replacement.append(new_token(char,style))
            changes.append((old_offsets[a],old_offsets[b],sum(len(t.raw)//2 for t in replacement)))
            result.extend(replacement)
    return result,changes


def mapped_position(position,changes,right=False):
    delta=0
    for lo,hi,length in changes:
        if position<lo:break
        if position<hi or position==lo==hi:return lo+delta+(length if right else 0)
        delta+=length-(hi-lo)
    return position+delta


class HwpNative:
    def __init__(self,path,work,java_entry):
        self.path=Path(path);self.work=Path(work);self.java_entry=java_entry
        self.streams={};self.directories={};self.sections={};self.fields={};self.paragraphs={};self.images=[]
        self.pending={};self.image_changes={};self.warnings=[];self.blockers=[]

    def java(self,*args):
        try:subprocess.run([*self.java_entry,*map(str,args)],timeout=45,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except (subprocess.SubprocessError,OSError):raise FormatError('HWP 기록을 읽거나 새 파일로 검증하지 못했습니다. 문서 구조와 Java 설치를 확인해 주세요.')

    def load(self):
        package=self.work/'hwp-read.streams';self.java('unpack',self.path,package)
        self.streams,self.directories=package_read(package.read_bytes());package.unlink()
        header=self.streams.get('FileHeader',b'')
        if len(header)<40 or header[:17]!=b'HWP Document File' or header[35]!=5:raise FormatError('HWP 5 문서만 원본 위치를 연결해 수정할 수 있습니다.')
        self.flags=struct.unpack_from('<I',header,36)[0];self.compressed=bool(self.flags&1)
        if self.flags&((1<<1)|(1<<2)|(1<<4)|(1<<8)|(1<<10)):
            raise FormatError('암호화·배포 제한·DRM이 적용된 HWP는 수정 사본을 만들 수 없습니다.')
        raw_info=self.streams.get('DocInfo')
        if raw_info is None:raise FormatError('HWP 문서 정보가 없습니다.')
        info=inflate(raw_info) if self.compressed else raw_info
        self.doc_info=records(info)
        if any(record.tag in {96,97} and record.data for record in self.doc_info):
            self.blockers.append('변경 추적 내용·작성자 기록이 있는 HWP는 해당 기록의 개인정보 제거를 검증할 수 없어 저장하지 않습니다. 변경 사항을 확정한 사본을 사용해 주세요.')
        expanded=len(info)
        for name in sorted(self.streams,key=lambda n:int(n.rsplit('Section',1)[1]) if re.fullmatch(r'BodyText/Section\d+',n) else -1):
            if not re.fullmatch(r'BodyText/Section\d+',name):continue
            data=inflate(self.streams[name]) if self.compressed else self.streams[name];expanded+=len(data)
            if expanded>MAX_EXPANDED:raise FormatError('HWP 본문 내부 크기가 처리 한도를 넘습니다.')
            self.sections[name]=records(data);self._fields(name)
        if not self.sections:raise FormatError('HWP 본문 구역을 찾지 못했습니다.')
        self._images()
        return self

    def _fields(self,name):
        items=self.sections[name];stack=[];controls=[];ordinal=0
        for index,item in enumerate(items):
            while stack and stack[-1][0]>=item.level:stack.pop()
            while controls and controls[-1][0]>=item.level:controls.pop()
            if item.tag==71:
                ident=item.data[:4][::-1].decode('ascii',errors='replace')
                controls.append((item.level,ident))
            if item.tag!=66:continue
            if len(item.data)<22:raise FormatError('HWP 문단 헤더가 잘렸습니다.')
            current=ordinal;ordinal+=1
            text_index=None;shape_index=None;related=[]
            for j in range(index+1,len(items)):
                child=items[j]
                if child.level<=item.level:break
                if child.level!=item.level+1:continue
                if child.tag==67:
                    if text_index is not None:raise FormatError('중복된 HWP 문단 텍스트는 수정할 수 없습니다.')
                    text_index=j
                elif child.tag==68:shape_index=j
                if child.tag in {68,69,70}:related.append(j)
            if text_index is None:continue
            shape=items[shape_index].data if shape_index is not None else b''
            if len(shape)%8:raise FormatError('HWP 글자 서식 위치가 올바르지 않습니다.')
            styles=list(struct.iter_unpack('<II',shape))
            data=items[text_index].data
            if struct.unpack_from('<I',item.data)[0]&0x7fffffff!=len(data)//2:raise FormatError('HWP 문단 글자 수가 기록과 일치하지 않습니다.')
            if struct.unpack_from('<H',item.data,12)[0]!=len(styles) or styles and (styles[0][0]!=0 or any(a[0]>b[0] for a,b in zip(styles,styles[1:])) or styles[-1][0]>len(data)//2):raise FormatError('HWP 문단의 글자 서식을 검증하지 못했습니다.')
            original=tokens(data,styles)
            self.paragraphs[(name,current)]={'header':index,'text':text_index,'shape':shape_index,'related':related,'tokens':original}
            segment=0;group=[];in_field=False
            context=' · '.join({'tbl ':'표','head':'머리말','foot':'꼬리말','fn  ':'각주','en  ':'미주','gso ':'도형','memo':'메모'}.get(v,'개체 내부') for _,v in controls)
            def add_group():
                target=(name,current,segment)
                text=''.join(t.text for t in group)
                self.fields[target]={'target':{'kind':'hwp','stream':name,'paragraph':current,'segment':segment},'text':text,'tokens':list(group),
                    'location':f'구역 {int(name.rsplit("Section",1)[1])+1} · '+(context+' · ' if context else '')+f'문단 {current+1} · 글자 구간 {segment+1}',
                    'editable':not in_field,'readOnlyReason':'필드 결과는 연결 정보가 다시 반영될 수 있어 이 글자 구간의 수정 저장을 지원하지 않습니다.' if in_field else ''}
            for token in original:
                if token.text is not None:group.append(token)
                else:
                    add_group();group=[];segment+=1
                    code=struct.unpack_from('<H',token.raw)[0]
                    if code==3:in_field=True
                    elif code==4:in_field=False
            add_group()

    def _images(self):
        referenced=set()
        for index,record in enumerate(self.doc_info):
            if record.tag!=18:continue
            if len(record.data)<2:raise FormatError('HWP 내장 데이터 정보가 잘렸습니다.')
            flags=struct.unpack_from('<H',record.data)[0];kind=flags&15
            if kind==0:
                self.blockers.append('외부 파일에 연결된 HWP 그림은 원본 내용을 검증할 수 없어 저장하지 않습니다. 그림을 문서에 포함한 사본을 사용해 주세요.');continue
            if kind!=1 or len(record.data)<6:
                self.blockers.append('첨부·OLE 저장 개체가 있는 HWP는 내부 내용의 제거를 검증할 수 없어 수정 저장을 지원하지 않습니다.');continue
            ident,length=struct.unpack_from('<HH',record.data,2)
            if 6+length*2!=len(record.data):raise FormatError('HWP 내장 데이터 확장자 정보가 올바르지 않습니다.')
            extension=record.data[6:].decode('utf-16-le');matches=[n for n in self.streams if n.casefold()==f'bindata/bin{ident:04x}.{extension}'.casefold()]
            if len(matches)!=1:raise FormatError('HWP 내장 이미지의 원본 위치를 확인할 수 없습니다.')
            name=matches[0];mode=(flags>>4)&3;compressed=self.compressed if mode==0 else mode==1
            if name in referenced or mode==3:
                raise FormatError('HWP 내장 데이터의 연결·압축 정보가 중복되거나 올바르지 않습니다.')
            referenced.add(name)
            raw=inflate(self.streams[name]) if compressed else self.streams[name]
            if extension.casefold() not in {'png','jpg','jpeg','bmp','gif','tif','tiff'}:
                self.blockers.append('지원하지 않는 HWP 내장 데이터가 있어 내용을 검증한 사본을 만들 수 없습니다.');continue
            self.images.append({'name':name,'raw':raw,'info':index,'compressed':compressed,'id':ident})
        if any(name.casefold().startswith('bindata/') and name not in referenced for name in self.streams):
            self.blockers.append('원본 연결을 확인할 수 없는 HWP 내장 데이터가 있어 남은 개인정보를 검증한 사본을 만들 수 없습니다.')

    def value(self,target):return self.fields.get((target['stream'],target['paragraph'],target['segment']),{}).get('text')

    def edit(self,target,new):
        key=(target['stream'],target['paragraph'],target['segment']);field=self.fields.get(key)
        if not field or not field['editable']:raise FormatError('이 HWP 글자 구간은 직접 수정할 수 없습니다.')
        if not isinstance(new,str) or len(new)>12000 or '\r' in new:raise FormatError('HWP 수정 문구는 12,000자 이하이며 줄바꿈은 LF 형식이어야 합니다.')
        for char in new:new_token(char,0)
        self.pending[key]=new

    def image_edit(self,name,raw):
        if not any(item['name']==name for item in self.images):raise FormatError('HWP 이미지 수정 위치가 올바르지 않습니다.')
        self.image_changes[name]=raw

    def _paragraph_edit(self,name,number):
        paragraph=self.paragraphs[(name,number)];items=self.sections[name]
        output=[];changes=[];segment=0;group=[]
        def flush():
            key=(name,number,segment)
            if key in self.pending:
                new,edits=changed_tokens(group,self.pending[key]);output.extend(new);changes.extend(edits)
            else:output.extend(group)
        for token in paragraph['tokens']:
            if token.text is not None:group.append(token)
            else:flush();group=[];output.append(token);segment+=1
        flush();changes.sort()
        items[paragraph['text']].data=b''.join(t.raw for t in output)
        shapes=[];position=0
        for token in output:
            if not shapes or shapes[-1][1]!=token.style:shapes.append((position,token.style))
            position+=len(token.raw)//2
        header=bytearray(items[paragraph['header']].data)
        original=struct.unpack_from('<I',header)[0]
        struct.pack_into('<I',header,0,(original&0x80000000)|position)
        mask=struct.unpack_from('<I',header,4)[0]
        for code in (9,10):mask=(mask&~(1<<code))|((1<<code) if any(struct.unpack_from('<H',t.raw)[0]==code for t in output) else 0)
        struct.pack_into('<I',header,4,mask)
        if paragraph['shape'] is not None:
            items[paragraph['shape']].data=b''.join(struct.pack('<II',*entry) for entry in shapes)
            struct.pack_into('<H',header,12,len(shapes))
        struct.pack_into('<H',header,16,0)
        items[paragraph['header']].data=bytes(header)
        for index in paragraph['related']:
            record=items[index]
            if record.tag==69:record.data=b''
            if record.tag==70:
                if len(record.data)%12:raise FormatError('HWP 범위 표시 기록이 올바르지 않습니다.')
                raw=bytearray(record.data)
                for at in range(0,len(raw),12):
                    a,b=struct.unpack_from('<II',raw,at)
                    if max(a,b)>len(b''.join(t.raw for t in paragraph['tokens']))//2:raise FormatError('HWP 범위 표시의 글자 위치가 올바르지 않습니다.')
                    struct.pack_into('<II',raw,at,mapped_position(a,changes),mapped_position(b,changes,True))
                record.data=bytes(raw)

    def export(self,output):
        if self.blockers:raise FormatError(self.blockers[0])
        changed_paragraphs={(name,number) for name,number,_ in self.pending}
        for name,number in changed_paragraphs:self._paragraph_edit(name,number)
        streams=dict(self.streams);directories=dict(self.directories)
        for name,items in self.sections.items():
            # A zero-length derived line cache is omitted. Other records keep
            # their original level and payload, including unknown object data.
            raw=record_bytes([r for r in items if not (r.tag==69 and not r.data)])
            streams[name]=deflate(raw) if self.compressed else raw
        for item in self.images:
            if item['name'] not in self.image_changes:continue
            raw=self.image_changes[item['name']];new=item['name'].rsplit('/',1)[0]+f'/BIN{item["id"]:04X}.png'
            if any(n!=item['name'] and n.casefold()==new.casefold() for n in streams):raise FormatError('HWP 내장 이미지 이름이 충돌합니다.')
            del streams[item['name']];streams[new]=deflate(raw) if item['compressed'] else raw
            record=self.doc_info[item['info']];record.data=record.data[:4]+struct.pack('<H',3)+'png'.encode('utf-16-le')
        info=record_bytes(self.doc_info);streams['DocInfo']=deflate(info) if self.compressed else info
        for name in list(streams):
            if name.split('/')[0].casefold() in REMOVED_ROOTS or name.startswith('\x05'):del streams[name]
        for name in list(directories):
            if name.split('/')[0].casefold() in REMOVED_ROOTS:del directories[name]
        header=bytearray(streams['FileHeader']);struct.pack_into('<I',header,36,self.flags&~((1<<3)|(1<<5)|(1<<6)|(1<<7)|(1<<9)))
        streams['FileHeader']=bytes(header)
        # Cached strings in opaque fields cannot be silently treated as erased.
        # Other editable paragraph occurrences are intentionally left alone:
        # users may have explicitly kept/excluded that separate occurrence.
        erased=set()
        for key,new in self.pending.items():
            old=self.fields[key]['text']
            for tag,a,b,_,_ in SequenceMatcher(None,old,new,autojunk=False).get_opcodes():
                value=old[a:b]
                identifiable=any(char.isalnum() for char in value) or len(value.strip())>=3
                if tag!='equal' and value.strip() and identifiable and value not in new:erased.add(value)
        opaque=[record.data for record in self.doc_info]
        opaque.extend(record.data for items in self.sections.values() for record in items if record.tag not in {66,67,68,69,70})
        for name,raw in streams.items():
            if name in self.sections or name in {'FileHeader','DocInfo'} or name.casefold().startswith('bindata/'):continue
            opaque.append(raw)
            try:opaque.append(inflate(raw))
            except FormatError:pass
        for value in erased:
            patterns=[value.encode('utf-16-le'),value.encode('utf-8')]
            if any(pattern in raw for pattern in patterns for raw in opaque):
                raise FormatError('가리려는 원문이 HWP의 별도 연결·개체·부가 기록에도 남아 있어 제거를 검증하지 못했습니다. 해당 기록을 정리한 사본을 사용해 주세요.')
        package=self.work/'hwp-write.streams';package.write_bytes(package_write(streams,directories))
        self.java('pack',package,output);package.unlink()
        check=HwpNative(output,self.work/'hwp-audit',self.java_entry)
        check.work.mkdir(exist_ok=True);check.load()
        # Compare every stream, including metadata removal and opaque records.
        if check.streams!=streams or check.directories!=directories:raise FormatError('HWP 저장 후 원본 구조·이미지 기록 검증에 실패했습니다.')
        for key,want in self.pending.items():
            if check.fields.get(key,{}).get('text')!=want:raise FormatError('HWP 수정 위치의 실제 텍스트를 검증하지 못했습니다.')
        self.java(output,self.work/'hwp-independent-text.txt')
