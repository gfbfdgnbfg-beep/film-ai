'use strict';
let current=null;
const byId=id=>document.getElementById(id);
chrome.tabs.query({active:true,currentWindow:true},tabs=>{
  current=tabs[0]||null;
  byId('tab').textContent=current?(current.title||'Tab không có tiêu đề')+'\n'+(current.url||''):'Không tìm thấy tab đang hoạt động';
});
byId('clipboard').addEventListener('click',async()=>{
  try{byId('prompt').value=await navigator.clipboard.readText();byId('message').textContent='Đã lấy prompt từ clipboard.'}
  catch(e){byId('message').textContent='Không đọc được clipboard; bạn có thể Ctrl+V vào khung.'}
});
byId('insert').addEventListener('click',async()=>{
  const prompt=byId('prompt').value.trim();
  if(!prompt||!current){byId('message').textContent='Chưa có tab hoặc prompt.';return;}
  if(!/^https?:\/\//.test(current.url||'')){byId('message').textContent='Chỉ hỗ trợ trang HTTP/HTTPS.';return;}
  try{
    const result=await chrome.scripting.executeScript({target:{tabId:current.id},args:[prompt],func:text=>{
      const visible=el=>{const b=el.getBoundingClientRect();return b.width>0&&b.height>0};
      const focus=document.activeElement;
      let el=(focus&&(focus.matches('textarea,input:not([type]),input[type="text"],[contenteditable="true"],[role="textbox"]'))&&visible(focus))?focus:null;
      if(!el)el=[...document.querySelectorAll('textarea,[contenteditable="true"],[role="textbox"],input[type="text"]')].find(visible);
      if(!el)return 'Không tìm thấy ô nhập. Hãy click ô prompt trên trang rồi bấm lại.';
      el.focus();
      if(el instanceof HTMLInputElement||el instanceof HTMLTextAreaElement){
        const proto=el instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto,'value').set.call(el,text);
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true}));
      }else{
        el.textContent=text;
        el.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:text}));
      }
      return 'Đã dán prompt. Hãy kiểm tra nội dung và tự nhấn tạo.';
    }});
    byId('message').textContent=result[0]?.result||'Đã gửi lệnh vào tab.';
  }catch(e){byId('message').textContent='Tab này không cho tiện ích can thiệp, hãy dán thủ công.';}
});
