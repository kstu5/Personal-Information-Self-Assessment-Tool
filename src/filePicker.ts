type ReadHandle={getFile():Promise<File>};
export type InspectionPicker=(options:object)=>Promise<ReadHandle[]>;

/** Prefer the operating system picker; an absent API leaves the input fallback. */
export async function pickInspectionFiles(picker?:InspectionPicker):Promise<File[]|null|undefined>{
  if(!picker)return undefined;
  try{
    const handles=await picker({id:'privacy-document-inspection',multiple:true,excludeAcceptAllOption:false,
      types:[
        {description:'문서 파일',accept:{'application/octet-stream':['.hwp','.hwpx','.docx','.xlsx','.pptx','.pdf','.csv','.tsv','.txt']}},
        {description:'이미지 파일',accept:{'image/png':['.png'],'image/jpeg':['.jpg','.jpeg']}},
      ]});
    return await Promise.all(handles.map(handle=>handle.getFile()));
  }catch(error){
    if(error instanceof DOMException&&error.name==='AbortError')return null;
    throw error;
  }
}
