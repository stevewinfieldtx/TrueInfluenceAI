<script>
const SLUG="__SLUG__";
const CH="__CH__";
const BIGBET="__BIGBET__";
let lastContent="";

function closeWriter(){document.getElementById("writerOverlay").classList.remove("active")}
function copyContent(){navigator.clipboard.writeText(lastContent).then(function(){var b=document.querySelector(".wm-btn-copy");b.textContent="\u2705 Copied!";setTimeout(function(){b.textContent="\ud83d\udccb Copy"},2000)})}

function _openModal(title,loadingMsg){
  var o=document.getElementById("writerOverlay"),c=document.getElementById("wmContent"),t=document.getElementById("wmTitle");
  t.textContent=title;
  c.innerHTML='<div class="wm-loading"><div class="spinner"></div><div>'+loadingMsg+'</div></div>';
  o.classList.add("active");
  return {o:o,c:c,t:t};
}

async function _callServer(payload){
  var r=await fetch("/api/write/"+SLUG,{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(payload)
  });
  var d=await r.json();
  if(d.error) throw new Error(d.error);
  return d.content||"No content generated.";
}

async function writeIt(btn){
  var type=btn.dataset.type,topic=btn.dataset.topic,views=btn.dataset.views||"";
  btn.disabled=true;btn.textContent="\u23f3 WRITING...";
  var m=_openModal("\u270d\ufe0f "+topic,"Writing in "+CH+"'s voice...");
  try{
    var text=await _callServer({topic:topic,type:"write",card_type:type,views:views});
    lastContent=text;
    m.c.innerHTML='<div class="wm-content">'+text.replace(/\n/g,"<br>")+'</div>';
  }catch(e){m.c.innerHTML='<div style="color:#f87171">Error: '+e.message+'</div>'}
  btn.disabled=false;btn.textContent="\u270d\ufe0f WRITE IT";
}

async function startIt(btn){
  var type=btn.dataset.type,topic=btn.dataset.topic,views=btn.dataset.views||"";
  btn.disabled=true;btn.textContent="\u23f3 THINKING...";
  var m=_openModal("\ud83d\ude80 Getting You Started: "+topic,"Building your starting framework...");
  try{
    var text=await _callServer({topic:topic,type:"start",card_type:type,views:views});
    lastContent=text;
    m.c.innerHTML='<div class="wm-content">'+text.replace(/\n/g,"<br>")+'</div>';
  }catch(e){m.c.innerHTML='<div style="color:#f87171">Error: '+e.message+'</div>'}
  btn.disabled=false;btn.textContent="\ud83d\ude80 START IT";
}

async function explainMore(btn){
  var topic=btn.dataset.topic,bigbet=btn.dataset.bigbet||BIGBET,label=btn.dataset.label||"";
  btn.disabled=true;btn.textContent="\u23f3 ANALYZING...";
  var m=_openModal("\ud83d\udd0d Deep Dive: "+label,"Building deep explanation...");
  try{
    var text=await _callServer({topic:topic,type:"explain",big_bet:bigbet,label:label});
    lastContent=text;
    m.c.innerHTML='<div class="wm-content">'+text.replace(/\n/g,"<br>")+'</div>';
  }catch(e){m.c.innerHTML='<div style="color:#f87171">Error: '+e.message+'</div>'}
  btn.disabled=false;btn.textContent="\ud83d\udd0d Explain More";
}
</script>