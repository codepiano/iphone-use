#!/usr/bin/env python3
"""Serve the actual panel with a synthetic MCP host and a captured single H.264 AU.

No daemon/phone credentials or personal state. Use chrome-use for actual browser
checks; this proves browser codec/canvas behavior, not a real MCP host product.
"""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--packet", required=True, type=Path, help="single Annex-B keyframe with SPS/PPS")
args = parser.parse_args()
packet = base64.b64encode(args.packet.read_bytes()).decode()
page = (Path(__file__).resolve().parent.parent / "crates/mcp/src/screen.html").read_text()
host = '''<!doctype html><title>Native panel video fixture</title>
<button id="hide">Hide screen</button><button id="show">Show screen</button>
<output id="state">public</output><iframe id="panel" width="360" height="800" sandbox="allow-scripts allow-same-origin"></iframe>
<script>
const frame=document.getElementById('panel');let hidden=false,scope=0,serial=0;
frame.src='/screen'+location.search;
document.getElementById('hide').onclick=()=>{hidden=true;scope++;document.getElementById('state').textContent='private';};
document.getElementById('show').onclick=()=>{hidden=false;scope++;document.getElementById('state').textContent='public';};
window.addEventListener('message',event=>{
 if(event.source!==frame.contentWindow || !event.data || event.data.id===undefined)return;
 const request=event.data;let result;
 if(request.method==='ui/initialize')result={hostContext:{}};
 else if(request.method==='tools/call'||request.method==='resources/read') {
  const video=request.method==='tools/call'?request.params.arguments.video:request.params.uri.includes('/video-v1/');
  const reset=request.method==='tools/call'?request.params.arguments.reset:request.params.uri.includes('/video-v1/1/');
  const body=hidden?{private_secs:60,clear_frame:true,frame:null}:{drivable:true,video:{format:'iphone-use-h264-annexb-v1',scope:'fixture-'+scope,reset,packets:[{keyframe:true,pts_micros:++serial*33333,data:'__PACKET__'}]}};
  if(!hidden && !video){body.error='fixture supplies native video only';body.frame=null;}
  result=request.method==='tools/call'?{structuredContent:body}:{contents:[{text:JSON.stringify(body)}]};
 } else return;
 frame.contentWindow.postMessage({jsonrpc:'2.0',id:request.id,result},'*');
});
</script>'''.replace('__PACKET__', packet)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/screen'):
            resources = 'resources=1' in self.path
            text = page.replace('__IU_VERSION__', 'fixture').replace('__IU_FRAME_TOOL__', 'phone_screen_frame')
            text = text.replace('__IU_RESOURCE_FRAMES__', str(resources).lower())
            text = text.replace('__IU_FRAME_RESOURCE__', 'ui://iphone-use/frame-v1/').replace('__IU_VIDEO_RESOURCE__', 'ui://iphone-use/video-v1/')
        elif self.path == '/' or self.path.startswith('/?'):
            text = host
        else:
            self.send_error(404)
            return
        data = text.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        if self.path.startswith('/screen'):
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
print(f'http://127.0.0.1:{server.server_port}/', flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
