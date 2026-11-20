"""Run the actual dashboard JavaScript with a minimal DOM to catch runtime errors."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_dashboard_bootstrap_and_review(tmp_path):
    if not shutil.which('node'):
        pytest.skip('Node is needed for the dashboard JavaScript smoke test')
    import web_ui
    script = web_ui.index_html().split('<script>')[1].split('</script>')[0]
    harness = r'''
const assert = require('node:assert/strict');
class Element {
  constructor(){this.children=[];this.style={};this.value='';this.hidden=false;this.className='';}
  append(...items){this.children.push(...items);}
  appendChild(item){this.append(item);}
  replaceChildren(...items){this.children=items;}
  add(item){this.append(item);}
  setAttribute(){}
}
const elements=new Map();
global.document={getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement(){return new Element();}};
global.localStorage={getItem(){return null;},setItem(){}};
global.Option=class extends Element {constructor(text,value){super();this.text=text;this.value=value;}};
global.fetch=async()=>({ok:true,json:async()=>({encoder:'libx264',count:0,reels:[],jobs:[]})});
global.alert=message=>{throw Error(message);};
'''
    assertions = r'''
reviewData={manifest:{reels:[{name:'test',title:'Test',layout:'crop',ranges:[[0,2]]}]},transcript:{segments:[{start:0,end:2,text:'Test sentence.',words:[{word:'Test'}]}]}};
drawCandidates();
assert.equal(document.getElementById('candidate-list').children.length,1);
const row=document.getElementById('candidate-list').children[0];
const correction=row.children.find(x=>x.value==='Test sentence.');
assert.ok(correction);
correction.value='Corrected sentence.';correction.onchange();
assert.equal(reviewData.transcript.segments[0].text,'Corrected sentence.');
assert.deepEqual(reviewData.transcript.segments[0].words,[]);
assert.ok(row.children.some(x=>x.textContent==='Preview framing and captions (8 sec)'));
console.log('Dashboard bootstrap and candidate editing passed');
'''
    path = tmp_path / 'dashboard.cjs'
    path.write_text(harness + script + assertions, encoding='utf-8')
    result = subprocess.run(['node', str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
