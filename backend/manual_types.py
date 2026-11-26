"""User-selected categories; no detector training or reclassification of source."""
from functools import lru_cache
import re
from backend.documents import DocumentError,MAX_BODY,MAX_TITLE


@lru_cache(maxsize=1)
def manual_types():
    from ko_pii.labels import LABEL_INFO
    from ko_pii.legal.mapping import risk_floor_for
    from backend.credentials import LABEL_NAMES
    preferred=['PERSON','PHONE','EMAIL','ADDRESS','DT_BIRTH','AGE','RRN','FRN','PASSPORT','DRIVER_LICENSE','CARD','ACCOUNT','API_KEY','PASSWORD']
    names={**{label:value[0] for label,value in LABEL_INFO.items()},**LABEL_NAMES}
    labels=preferred+[label for label in names if label not in preferred]
    return [{'label':'USER_DEFINED','labelName':'사용자 추가','risk':'INFO'}]+[
        {'label':label,'labelName':names[label],'risk':'CRITICAL' if label in LABEL_NAMES else (risk_floor_for(label).name if risk_floor_for(label) else 'INFO')}
        for label in labels]


def manual_type(label):
    value=next((item for item in manual_types() if item['label']==label),None)
    if value is None:raise DocumentError('지원하는 개인정보 유형을 선택해 주세요.')
    return dict(value)


def manual_proposal(label,text,seeds):
    from backend.auto_mask import ALIASES,proposals
    metadata=manual_type(label)
    if not isinstance(text,str) or not text.strip() or len(text)>MAX_BODY+MAX_TITLE or any(0xd800<=ord(c)<=0xdfff for c in text):raise DocumentError('원문에서 추가할 내용을 다시 선택해 주세요.')
    if len(seeds)>6000:raise DocumentError('대체 표시 정보가 처리 한도를 넘습니다.')
    aliases={};used=set();size=0
    for seed in seeds:
        category,value,alias=seed['label'],seed['text'],seed['alias'];size+=len(value)
        if category not in ALIASES or size>MAX_BODY+MAX_TITLE or not re.fullmatch(re.escape(ALIASES[category])+r' [A-Z]{1,5}',alias) or (category,value) in aliases or (category,alias) in used:
            raise DocumentError('현재 게시글의 대체 표시 정보를 다시 확인해 주세요.')
        aliases[category,value]=alias;used.add((category,alias))
    proposal=proposals([{'id':'manual','text':text,**metadata}],aliases,scope='post')['manual']
    return {**metadata,'autoMask':proposal,'aliases':[{'label':key[0],'text':key[1],'alias':alias} for key,alias in aliases.items()]}
