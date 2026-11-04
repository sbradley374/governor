const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function ambient(reduced = false) {
  let now = 1000, timer, keydown, seed = 17;
  const states = [], elements = {};
  const randomMath = Object.create(Math);
  randomMath.random = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
  const scope = {performance:{now:()=>now}, Math:randomMath,
    matchMedia:()=>({matches:reduced}), localStorage:{getItem:()=>null,setItem(){}},
    document:{hidden:false,documentElement:{style:{}},getElementById:id=>elements[id]||(elements[id]={style:{},hidden:true}),
      addEventListener:(_,fn)=>{keydown=fn;}},
    window:{governorFace:{setState:s=>states.push(s)}}, setInterval:fn=>{timer=fn;}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../governor/static/ambient.js'),'utf8'),scope);
  return {states,scope,advance:ms=>{now+=ms;timer();},key:key=>keydown({key,repeat:false,preventDefault(){}})};
}
test('offline face runs varied routines without network, audio, or hardware APIs',()=>{
  const a=ambient();
  for(let i=0;i<120;i++)a.advance(1000);
  assert.ok(new Set(a.states.map(s=>s.emotion)).size>=4);
  assert.ok(a.states.some(s=>Math.abs(s.pose.x)>1));
  assert.ok(a.states.every(s=>s.status==='idle'));
});
test('pause keeps the face resting and color controls work locally',()=>{
  const a=ambient();a.key(' ');a.advance(30000);
  assert.equal(a.states.at(-1).paused,true);
  a.key('c');assert.equal(a.states.at(-1).display.palette,'amber');
  a.key(' ');assert.equal(a.states.at(-1).paused,false);
});
test('reduced motion disables automatic gaze and mood routines',()=>{
  const a=ambient(true);a.advance(60000);
  assert.equal(a.states.at(-1).emotion,'neutral');
  assert.equal(a.states.at(-1).pose.x,0);
});
