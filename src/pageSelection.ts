import type {Box,FilePart,PageTextRange} from './documentTypes.ts';
import type {SourceRange} from './sourceSelection.ts';

export type PageGlyph={part:string;start:number;end:number;box:Box};
const segmenter=new Intl.Segmenter('ko',{granularity:'grapheme'});

export function pageGlyphs(ranges:PageTextRange[],parts:FilePart[],page:number):PageGlyph[]{
  const byPart=new Map(parts.map(p=>[p.id,p]));
  const boundaries=new Map<string,Map<number,[number,number]>>(),groups=new Map<string,PageGlyph[]>();
  for(const item of ranges){
    if(item.page!==page)continue;
    const part=byPart.get(item.part);if(!part)continue;
    let offsets=boundaries.get(part.id);
    if(!offsets){
      offsets=new Map();
      for(const s of segmenter.segment(part.text))for(let i=s.index;i<s.index+s.segment.length;i++)offsets.set(i,[s.index,s.index+s.segment.length]);
      boundaries.set(part.id,offsets);
    }
    for(const [lo,hi,x0,y0,x1,y1] of item.characters){
      const a=offsets.get(lo),b=offsets.get(hi-1);
      if(!a||!b||hi<=lo||![x0,y0,x1,y1].every(Number.isFinite)||x1<=x0||y1<=y0)continue;
      const start=a[0],end=b[1],key=`${part.id}:${start}:${end}`,same=groups.get(key)||[];
      const nearby=same.find(g=>g.box[0]<=x1+1&&g.box[2]>=x0-1&&g.box[1]<=y1+1&&g.box[3]>=y0-1);
      if(nearby)nearby.box=[Math.min(nearby.box[0],x0),Math.min(nearby.box[1],y0),Math.max(nearby.box[2],x1),Math.max(nearby.box[3],y1)];
      else same.push({part:part.id,start,end,box:[x0,y0,x1,y1]});
      groups.set(key,same);
    }
  }
  return [...groups.values()].flat();
}

export function nearestGlyph(glyphs:PageGlyph[],x:number,y:number,part?:string,tolerance=Infinity):PageGlyph|null {
  let best:PageGlyph|null=null,distance=Infinity,ambiguous=false;
  for(const g of glyphs){
    if(part&&g.part!==part)continue;
    const [x0,y0,x1,y1]=g.box,dx=Math.max(x0-x,0,x-x1),dy=Math.max(y0-y,0,y-y1),d=dx*dx+dy*dy;
    if(d<distance){best=g;distance=d;ambiguous=false;}
    else if(d===distance&&best?.part!==g.part)ambiguous=true;
  }
  return !ambiguous&&distance<=tolerance*tolerance?best:null;
}

export function glyphCaret(glyph:PageGlyph,x:number):number {
  return x<(glyph.box[0]+glyph.box[2])/2?glyph.start:glyph.end;
}

export function pageRange(part:string,start:number,end:number):SourceRange|null {
  return start===end?null:{part,start:Math.min(start,end),end:Math.max(start,end)};
}

export function rangeBoxes(glyphs:PageGlyph[],range:SourceRange):Box[]{
  const boxes=glyphs.filter(g=>g.part===range.part&&g.start<range.end&&g.end>range.start).map(g=>g.box);
  const lines:Box[]=[];
  for(const box of boxes.sort((a,b)=>a[1]-b[1]||a[0]-b[0])){
    const line=lines.find(b=>Math.abs(b[1]-box[1])<2&&Math.abs(b[3]-box[3])<2&&box[0]-b[2]<8&&box[2]>=b[0]);
    if(line){line[0]=Math.min(line[0],box[0]);line[2]=Math.max(line[2],box[2]);}
    else lines.push([...box]);
  }
  return lines;
}
