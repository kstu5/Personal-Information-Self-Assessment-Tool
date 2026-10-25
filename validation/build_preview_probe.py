"""Build a local read-only illustration from an actual prior synthetic-model result.

The probe deliberately exposes ambiguous value matches. It is not an editing UI
or a verified mapping from preview pixels to source XML.
"""
from pathlib import Path
import base64
import json
import sys
ROOT=Path(__file__).resolve().parents[1]

def main():
    run=Path(sys.argv[1]).resolve()
    allowed=(ROOT/'validation/qa/preview-research').resolve()
    assert run.is_relative_to(allowed)
    probe=json.loads((run/'mapping-probe.json').read_text('utf-8'))
    png=run/'0-0/page-1.png'
    from PIL import Image
    with Image.open(png) as im:width,height=im.size
    # PDF coordinates are in points; the stored PNG uses a scale of 1.5.
    payload={'candidates':probe['candidates'],'width':width,'height':height,
             'image':'data:image/png;base64,'+base64.b64encode(png.read_bytes()).decode('ascii')}
    html='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>문서 화면 연결 확인 시안</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6f8;color:#233241;font:14px 'Malgun Gothic',sans-serif}
header{padding:22px 30px;background:white;border-bottom:1px solid #dde4ea}h1{font-size:22px;margin:0 0 8px}p{line-height:1.7;margin:0;color:#5b6c7a}
.top{display:flex;justify-content:space-between;align-items:center;gap:20px}.label{color:#547362;font-size:12px}.layout{display:grid;grid-template-columns:minmax(500px,1fr) 365px;gap:20px;padding:22px;max-width:1460px;margin:auto}
section,aside{background:white;border:1px solid #dce4ea;border-radius:12px;overflow:hidden}.bar{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;border-bottom:1px solid #e5ebee}h2{font-size:16px;margin:0}
.viewport{height:calc(100vh - 232px);min-height:470px;overflow:auto;background:#e8edf1;padding:22px}.paper{position:relative;max-width:850px;margin:auto;background:white;box-shadow:0 3px 12px #22334418}.paper img{width:100%;display:block}
.hit{position:absolute;background:color-mix(in srgb,var(--color) 13%,transparent);border:2px solid var(--color);border-radius:2px;cursor:pointer;padding:0;min-width:4px;min-height:4px}.hit.ambiguous{border-style:dashed}.hit.focus{background:color-mix(in srgb,var(--color) 35%,transparent);box-shadow:0 0 0 3px #263e5a55}
.cards{height:calc(100vh - 285px);min-height:400px;overflow:auto;padding:8px 12px}.card{display:block;width:100%;text-align:left;padding:13px 12px;margin:6px 0;border:1px solid #e0e7ec;border-left:4px solid var(--color);background:white;border-radius:7px;cursor:pointer;color:inherit}.card.active{background:#eff5fb;border-color:#3d698c}.card strong{display:block;font-size:14px;margin:6px 0;overflow-wrap:anywhere}.card small{display:block;line-height:1.7;color:#667986;font-size:11px}.meta{font-size:11px;color:var(--color);font-weight:bold}.status{float:right;color:#697b86;font-size:10px}.foot{padding:12px 20px;border-top:1px solid #e5ebee;font-size:12px;min-height:56px;line-height:1.6}
button,select{font:inherit}select{padding:6px;border:1px solid #d9e2e9;border-radius:5px;color:#435c70;background:white}.note{margin-top:12px;color:#7b6437;font-size:12px}.legend{font-size:11px;color:#687c8c}.only{padding:6px 10px;background:#edf4ef;border-radius:5px;color:#476c57;font-size:11px;white-space:nowrap}
@media(min-width:951px){body{height:100vh;overflow:hidden}header{height:126px}.layout{height:calc(100vh - 126px);padding:20px}section,aside{display:flex;flex-direction:column;min-height:0}.bar,.foot{flex-shrink:0}.viewport,.cards{height:auto;min-height:0;flex:1}}
@media(max-width:950px){.layout{grid-template-columns:1fr}.viewport{height:650px}.cards{height:400px}.top{align-items:start}.label{display:none}}
</style><header><div class="top"><div><div class="label">가상 문서로 확인하는 문서 화면 연결</div><h1>이력서의 개인정보 위치 확인</h1><p>문서의 색상 표시나 오른쪽 항목을 눌러 내용을 확인할 수 있습니다.</p></div><span class="only">읽기 전용 확인 시안</span></div></header>
<div class="layout"><section><div class="bar"><h2>문서 화면</h2><span class="legend">실선 위치 한 곳 · 점선 같은 문구 여러 곳</span></div><div class="viewport"><div class="paper" id="paper"></div></div><div class="foot" id="detail">검출 항목을 선택하면 해당 문구가 있는 곳을 강조합니다. 이 화면은 수정 사본을 만들지 않습니다.</div></section>
<aside><div class="bar"><h2 id="count">검출 목록</h2><select id="filter" aria-label="위험도"><option value="all">전체 위험도</option><option value="HIGH">높음</option><option value="MEDIUM">보통</option><option value="LOW">낮음</option><option value="INFO">참고</option></select></div><p style="padding:12px 20px;font-size:12px">이전에 실제 모델로 검사한 가상 이력서 결과입니다. 목록의 원문 위치도 함께 확인해 주세요.</p><div class="cards" id="cards"></div></aside></div>
<script>const data=__DATA__;
const colors={CRITICAL:'#c62c43',HIGH:'#7c3aed',MEDIUM:'#2563eb',LOW:'#12817c',INFO:'#ac7908'};
const names={CRITICAL:'심각',HIGH:'높음',MEDIUM:'보통',LOW:'낮음',INFO:'참고'};
const paper=document.getElementById('paper'),cards=document.getElementById('cards');let focus=-1;
const image=document.createElement('img');image.src=data.image;image.alt='가상 이력서 문서 화면';paper.append(image);
const hits=new Map();data.candidates.forEach((c,i)=>c.render_hits.filter(h=>h.page===1).forEach(h=>{const key=h.box.map(v=>v.toFixed(1)).join(',');if(!hits.has(key))hits.set(key,{box:h.box,ids:[]});hits.get(key).ids.push(i)}));
const elements=[];for(const hit of hits.values()){const b=document.createElement('button'),c=data.candidates[hit.ids[0]];b.className='hit'+(hit.ids.some(i=>data.candidates[i].render_hits.length!==1)?' ambiguous':'');b.style.setProperty('--color',colors[c.risk]);const [a,t,r,d]=hit.box;b.style.left=(a*1.5/data.width*100)+'%';b.style.top=(t*1.5/data.height*100)+'%';b.style.width=((r-a)*1.5/data.width*100)+'%';b.style.height=((d-t)*1.5/data.height*100)+'%';b.setAttribute('aria-label',c.type+' '+c.text+' 위치 확인');b.title=c.type+' '+c.text;b.onclick=()=>select(hit.ids[0],false);paper.append(b);elements.push({b,ids:hit.ids});}
function select(i,scroll=true){focus=i;const c=data.candidates[i];for(const e of elements)e.b.classList.toggle('focus',e.ids.includes(i));for(const b of cards.children)b.classList.toggle('active',Number(b.dataset.index)===i);document.getElementById('detail').textContent=c.type+' '+c.text+' · 원문 위치 '+c.source_location+(c.render_hits.length===1?' · 문서 화면에서 문구 한 곳 확인':' · 같은 문구가 '+c.render_hits.length+'곳에 있습니다. 원문 위치와의 추가 연결이 필요합니다.');if(scroll){const hit=elements.find(e=>e.ids.includes(i));hit?.b.scrollIntoView({block:'center',behavior:'smooth'})}}
function render(){cards.replaceChildren();const filter=document.getElementById('filter').value;let n=0;data.candidates.forEach((c,i)=>{if(filter!=='all'&&c.risk!==filter)return;n++;const b=document.createElement('button');b.type='button';b.dataset.index=i;b.className='card'+(i===focus?' active':'');b.style.setProperty('--color',colors[c.risk]);const m=document.createElement('span');m.className='meta';m.textContent=names[c.risk]+' · '+c.type;const s=document.createElement('span');s.className='status';s.textContent=c.render_hits.length===1?'문구 한 곳':'위치 확인 필요';const v=document.createElement('strong');v.textContent=c.text;const l=document.createElement('small');l.textContent=c.source_location;b.append(m,s,v,l);b.onclick=()=>select(i);cards.append(b)});document.getElementById('count').textContent='검출 목록 '+n+'개';for(const e of elements)e.b.hidden=!e.ids.some(i=>filter==='all'||data.candidates[i].risk===filter)}
document.getElementById('filter').onchange=render;render();
</script></html>'''
    html=html.replace('__DATA__',json.dumps(payload,ensure_ascii=False).replace('<','\\u003c'))
    (run/'index.html').write_text(html,encoding='utf-8')
    print(run/'index.html')

if __name__=='__main__':main()
