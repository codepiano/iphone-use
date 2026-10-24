// Actual panel script, emulated MCP host/decoder. No rendering or device claim.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const html=fs.readFileSync(new URL('../crates/mcp/src/screen.html',import.meta.url),'utf8');
for (const resources of [false,true]) {
  const elements=new Map(),events=new Map(),timers=new Map(),messages=[];
  let timerId=0,now=0,privateScreen=false,unavailable=false,scope='boot-0',draws=0,closed=0;
  const outputs=[];
  const element=id=>{
    if(!elements.has(id))elements.set(id,{hidden:true,dataset:{},textContent:'',
      addEventListener(name,handler){this[name]=handler;},removeAttribute(name){delete this[name];},
      getContext(){return {drawImage(){draws++;}};}});
    return elements.get(id);
  };
  class Decoder {
    static async isConfigSupported(){return {supported:true};}
    constructor(callbacks){this.callbacks=callbacks;this.decodeQueueSize=0;}
    configure(){}
    close(){closed++;}
    decode(){const run=()=>this.callbacks.output({displayWidth:16,displayHeight:32,close(){}});outputs.push(run);queueMicrotask(run);}
  }
  const window={innerWidth:320,addEventListener(name,handler){events.set(name,handler);},parent:{postMessage(request){
    messages.push(request);if(!request.id)return;
    let result;
    if(request.method==='ui/initialize')result={hostContext:{}};
    else {
      let video,reset;
      if(resources){assert.equal(request.method,'resources/read');video=request.params.uri.includes('/video-v1/');reset=request.params.uri.includes('/video-v1/1/');}
      else {assert.equal(request.method,'tools/call');assert.equal(request.params.name,'phone_screen_frame');video=request.params.arguments.video;reset=request.params.arguments.reset;}
      let body={drivable:true,private_secs:privateScreen?60:null};
      if(privateScreen)body={...body,clear_frame:true};
      else if(video && unavailable)body={...body,clear_frame:true,video_unavailable:true,error:'not available'};
      else if(video)body={...body,video:{format:'iphone-use-h264-annexb-v1',scope,reset,packets:[{keyframe:true,pts_micros:1,data:Buffer.from([0,0,0,1,0x67,0x42,0,0x1f,0,0,0,1,0x65]).toString('base64')} ]}};
      else body={...body,frame:{mime_type:'image/png',data:'fixture'}};
      result=resources?{contents:[{text:JSON.stringify(body)}]}:{structuredContent:body};
    }
    queueMicrotask(()=>events.get('message')({source:window.parent,data:{jsonrpc:'2.0',id:request.id,result}}));
  }}};
  const document={hidden:false,title:'iPhone screen',body:{},documentElement:{dataset:{},getBoundingClientRect(){return {height:680};}},
    querySelectorAll(){return [];},getElementById:element,addEventListener(name,handler){events.set(name,handler);}};
  const script=html.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replaceAll('__IU_RESOURCE_FRAMES__',String(resources)).replaceAll('__IU_FRAME_RESOURCE__','ui://iphone-use/frame-v1/')
    .replaceAll('__IU_VIDEO_RESOURCE__','ui://iphone-use/video-v1/').replaceAll('__IU_FRAME_TOOL__','phone_screen_frame').replaceAll('__IU_VERSION__','test');
  vm.runInNewContext(script,{window,document,navigator:{language:'en'},performance:{now:()=>now},VideoDecoder:Decoder,
    EncodedVideoChunk:class {constructor(data){Object.assign(this,data);}},Uint8Array,atob:value=>Buffer.from(value,'base64').toString('binary'),
    setTimeout(handler,delay){timers.set(++timerId,{handler,delay});return timerId;},clearTimeout(id){timers.delete(id);},console});
  const flush=async()=>{for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));};
  const poll=async()=>{const item=[...timers].find(([,value])=>value.delay<8000);assert(item);timers.delete(item[0]);item[1].handler();await flush();};
  await flush();await poll();assert.equal(draws,1);assert.equal(element('video').hidden,false);assert.equal(element('image').hidden,true);
  privateScreen=true;await poll();assert.equal(element('video').hidden,true);assert.equal(element('video').width,1);
  const previous=draws;for(const output of outputs)output();assert.equal(draws,previous,'late decoder callbacks after private hold must not render');
  privateScreen=false;scope='boot-2';now=31000;await poll();assert.equal(draws,previous+1);assert(closed>0);
  unavailable=true;await poll();assert.equal(element('video').hidden,true);await poll();assert.equal(element('image').src,'data:image/png;base64,fixture');
  events.get('pagehide')();const reads=messages.length;for(const [id,timer]of [...timers])if(timer.delay<8000){timers.delete(id);timer.handler();}await flush();assert.equal(messages.length,reads);
  assert.equal(element('video').hidden,true);assert(!JSON.stringify(messages).includes('Bearer'));
  console.log(`ok - ${resources?'WorkBuddy resources':'generic/Doubao tools'}: native packets, privacy, late callbacks, reset, PNG fallback, hidden teardown`);
}
