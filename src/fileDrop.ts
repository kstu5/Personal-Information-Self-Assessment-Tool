type FileDragEvent = Pick<DragEvent,'dataTransfer'|'preventDefault'|'stopPropagation'>;

/** Keep nested drag events balanced and copy files before the drop event expires. */
export function createFileDropHandlers(options:{
  canAdd:()=>boolean;
  onFiles:(files:File[])=>void;
  onHover:(hover:boolean)=>void;
  onBlocked:()=>void;
  onEmpty:()=>void;
}) {
  let depth=0;
  const isFile=(event:FileDragEvent)=>!!event.dataTransfer&&Array.from(event.dataTransfer.types).includes('Files');
  function reset(){depth=0;options.onHover(false);}
  function enter(event:FileDragEvent){
    if(!isFile(event))return;
    event.preventDefault();depth++;options.onHover(true);
  }
  function over(event:FileDragEvent){
    if(!isFile(event))return;
    event.preventDefault();
    if(event.dataTransfer)event.dataTransfer.dropEffect=options.canAdd()?'copy':'none';
  }
  function leave(event:FileDragEvent){
    if(!isFile(event)&&!depth)return;
    depth=Math.max(0,depth-1);
    if(!depth)options.onHover(false);
  }
  function drop(event:FileDragEvent){
    if(!isFile(event))return;
    event.preventDefault();event.stopPropagation();reset();
    if(!options.canAdd()){options.onBlocked();return;}
    const files=Array.from(event.dataTransfer!.files);
    if(!files.length){options.onEmpty();return;}
    options.onFiles(files);
  }
  return {enter,over,leave,drop,reset};
}
