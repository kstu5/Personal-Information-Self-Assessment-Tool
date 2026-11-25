export type SourceRange={part:string;start:number;end:number};

export function sourceCaret(root:HTMLElement,x:number,y:number):Range|null {
  const hit=document.elementFromPoint(x,y)?.closest<HTMLElement>('[data-source-part]');
  if(!hit||!root.contains(hit)||hit.dataset.sourceSelectable!=='true')return null;
  const position=document.caretPositionFromPoint?.(x,y);
  const range=position?document.createRange():document.caretRangeFromPoint?.(x,y);
  if(position){range!.setStart(position.offsetNode,position.offset);range!.collapse(true);}
  if(!range)return null;
  const node=range.startContainer;
  const part=(node.nodeType===Node.ELEMENT_NODE?node as Element:node.parentElement)?.closest<HTMLElement>('[data-source-part]');
  return part&&root.contains(part)&&part.dataset.sourceSelectable==='true'?range:null;
}

/** DOM Range offsets and candidate offsets both use UTF-16 code units. */
export function readSourceRange(root:HTMLElement,selection:Selection|null):SourceRange|null {
  if(!selection||selection.isCollapsed||selection.rangeCount!==1)return null;
  const range=selection.getRangeAt(0);
  const source=(node:Node)=>(node.nodeType===Node.ELEMENT_NODE?node as Element:node.parentElement)?.closest<HTMLElement>('[data-source-part]');
  const first=source(range.startContainer),last=source(range.endContainer);
  if(!first||first!==last||!root.contains(first)||first.dataset.sourceSelectable!=='true')return null;
  const prefix=range.cloneRange();prefix.selectNodeContents(first);prefix.setEnd(range.startContainer,range.startOffset);
  const start=prefix.toString().length,end=start+range.toString().length;
  return end>start?{part:first.dataset.sourcePart!,start,end}:null;
}

export function rangeConflict(range:SourceRange,candidates:{id:string;part:string;start:number;end:number}[],replaceId?:string):boolean {
  return candidates.some(c=>c.id!==replaceId&&c.part===range.part&&range.start<c.end&&c.start<range.end);
}

export function showSourceRange(element:HTMLElement,start:number,end:number):void {
  if(element.dataset.sourceSelectable!=='true')return;
  const walker=document.createTreeWalker(element,NodeFilter.SHOW_TEXT);
  const range=document.createRange();let pos=0,started=false,node:Node|null;
  while((node=walker.nextNode())){
    const length=node.textContent?.length||0;
    if(!started&&start<=pos+length){range.setStart(node,start-pos);started=true;}
    if(started&&end<=pos+length){range.setEnd(node,end-pos);const selection=window.getSelection();selection?.removeAllRanges();selection?.addRange(range);return;}
    pos+=length;
  }
}
