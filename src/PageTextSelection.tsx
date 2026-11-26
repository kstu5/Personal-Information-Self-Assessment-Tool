import {useEffect,useMemo,useRef,useState} from 'react';
import type {FileAsset,FilePart,PageTextRange} from './documentTypes';
import type {SourceRange} from './sourceSelection';
import {glyphCaret,nearestGlyph,pageGlyphs,pageRange,rangeBoxes} from './pageSelection';

/** Capture on the image parent so candidate clicks and text drags coexist. */
export function PageTextSelection({asset,parts,ranges,page=0,enabled,onRange,resetKey}:{asset:FileAsset;parts:FilePart[];ranges:PageTextRange[];page?:number;enabled:boolean;onRange:(range:SourceRange)=>void;resetKey:string}){
  const overlay=useRef<HTMLDivElement>(null),callback=useRef(onRange);callback.current=onRange;
  const blockedUntil=useRef(0);
  const [selected,setSelected]=useState<SourceRange|null>(null);
  const glyphs=useMemo(()=>pageGlyphs(ranges,parts,page),[ranges,parts,page]);
  useEffect(()=>setSelected(null),[resetKey,enabled,page]);
  useEffect(()=>{
    const frame=overlay.current?.parentElement;
    if(!frame||!enabled||!glyphs.length)return;
    let anchor:{part:string;offset:number;x:number;y:number;pointer:number}|null=null;
    let selected:SourceRange|null=null,dragged=false;
    const point=(e:PointerEvent)=>{const r=frame.getBoundingClientRect();return {x:(e.clientX-r.left)*asset.width/r.width,y:(e.clientY-r.top)*asset.height/r.height,tolerance:5*asset.width/r.width};};
    const down=(e:PointerEvent)=>{
      if(e.button!==0)return;
      const p=point(e),g=nearestGlyph(glyphs,p.x,p.y,undefined,p.tolerance);
      anchor=null;dragged=false;selected=null;setSelected(null);
      if(!g)return;
      anchor={part:g.part,offset:glyphCaret(g,p.x),x:e.clientX,y:e.clientY,pointer:e.pointerId};
      window.getSelection()?.removeAllRanges();e.preventDefault();
    };
    const move=(e:PointerEvent)=>{
      if(!anchor||e.pointerId!==anchor.pointer||!(e.buttons&1))return;
      if(!dragged&&Math.hypot(e.clientX-anchor.x,e.clientY-anchor.y)<4)return;
      dragged=true;if(!frame.hasPointerCapture(e.pointerId))frame.setPointerCapture(e.pointerId);
      const p=point(e),g=nearestGlyph(glyphs,p.x,p.y,anchor.part);
      if(g){selected=pageRange(anchor.part,anchor.offset,glyphCaret(g,p.x));setSelected(selected);}
      e.preventDefault();e.stopPropagation();
    };
    const up=(e:PointerEvent)=>{
      if(!anchor||e.pointerId!==anchor.pointer)return;
      move(e);anchor=null;
      if(dragged){blockedUntil.current=Date.now()+150;e.preventDefault();e.stopPropagation();if(selected)callback.current(selected);}
      dragged=false;
    };
    const click=(e:MouseEvent)=>{if(Date.now()<blockedUntil.current){blockedUntil.current=0;e.preventDefault();e.stopPropagation();}};
    const cancel=()=>{anchor=null;selected=null;dragged=false;setSelected(null);};
    frame.classList.add('page-text-selectable');
    frame.addEventListener('pointerdown',down,true);frame.addEventListener('pointermove',move,true);frame.addEventListener('pointerup',up,true);frame.addEventListener('pointercancel',cancel,true);frame.addEventListener('click',click,true);
    return()=>{frame.classList.remove('page-text-selectable');frame.removeEventListener('pointerdown',down,true);frame.removeEventListener('pointermove',move,true);frame.removeEventListener('pointerup',up,true);frame.removeEventListener('pointercancel',cancel,true);frame.removeEventListener('click',click,true);};
  },[asset.width,asset.height,enabled,glyphs]);
  return <div className="page-text-selection" ref={overlay} aria-hidden="true">{enabled&&selected&&rangeBoxes(glyphs,selected).map((b,i)=><span key={i} style={{left:`${b[0]/asset.width*100}%`,top:`${b[1]/asset.height*100}%`,width:`${(b[2]-b[0])/asset.width*100}%`,height:`${(b[3]-b[1])/asset.height*100}%`}}/>)}</div>;
}
