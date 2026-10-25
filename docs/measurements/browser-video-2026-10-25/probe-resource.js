(() => {
const w=document.querySelector('#panel').contentWindow;
window.__videoProbe={configured:0,decoded:0,outputs:0,errors:[],supports:[],started:performance.now()};
window.__hostProbe={toolCalls:0,resourceReads:0};
window.addEventListener('message',event=>{if(event.source!==w)return;const m=event.data?.method;if(m==='tools/call')window.__hostProbe.toolCalls++;if(m==='resources/read')window.__hostProbe.resourceReads++;});
const state=window.__videoProbe,Original=w.VideoDecoder;
class Probe extends Original {
 static async isConfigSupported(c){const r=await Original.isConfigSupported(c);if(state.supports.length<5)state.supports.push({codec:c.codec,supported:r.supported});return r;}
 constructor(init){super({output(f){state.outputs++;state.lastOutput={width:f.displayWidth,height:f.displayHeight};init.output(f);},error(e){if(state.errors.length<10)state.errors.push({name:e.name,message:e.message});init.error(e);}});}
 configure(c){state.configured++;return super.configure(c);}
 decode(c){state.decoded++;return super.decode(c);}
}
w.VideoDecoder=Probe;
return JSON.stringify({installed:true,hidden:w.document.hidden,secure:w.isSecureContext});
})()