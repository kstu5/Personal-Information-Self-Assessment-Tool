/** Run after React commits the selected candidate and custom input. */
export function revealFileEditor(editor:HTMLElement|null,focusInput=false) {
  if(!editor)return;
  const input=editor.querySelector<HTMLInputElement>('#file-custom-input');
  if(focusInput&&input){
    input.focus({preventScroll:true});
    input.scrollIntoView({block:'center',behavior:'auto'});
    input.select();
  }else editor.scrollIntoView({block:'nearest',behavior:'auto'});
}
