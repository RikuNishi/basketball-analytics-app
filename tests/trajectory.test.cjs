const {test} = require('node:test');
const assert = require('node:assert/strict');
const {build, smooth} = require('../basket/static/trajectory.js');
const shot = {release_s:0,end_s:2};
const frame = (t,x=10,y=20,source='detected') => ({t,ball:{x,y,source}});

test('preserves a vertical parabola with irregular timestamps, without extrapolation',()=>{
  const points=[0,.03,.07,.1,.16,.2,.25,.31].map(t=>({t,x:12,y:200-300*t+100*t*t}));
  const curve=smooth(points);
  assert.equal(curve[0].t,0);assert.equal(curve.at(-1).t,.31);
  for(const p of curve){assert.ok(Math.abs(p.x-12)<1e-8);assert.ok(Math.abs(p.y-(200-300*p.t+100*p.t*p.t))<1e-8);}
});
test('reduces detection jitter on a curved flight',()=>{
  const truth=t=>50-100*t+80*t*t;
  const points=Array.from({length:61},(_,i)=>({t:i/60,x:i,y:truth(i/60)+(i%2?3:-3)}));
  const curve=smooth(points);
  assert.ok(curve.reduce((sum,p)=>sum+(p.y-truth(p.t))**2,0)/curve.length < 3);
});
test('ignores predictions, separates long gaps and leaves observations unchanged',()=>{
  const frames=[...Array.from({length:6},(_,i)=>frame(i*.02,i)),frame(.2,999,999,'predicted'),...Array.from({length:6},(_,i)=>frame(.5+i*.02,i))];
  const original=JSON.stringify(frames), result=build(frames,shot);
  assert.equal(result.curves.length,2);assert.equal(result.points.length,12);
  assert.ok(result.curves[0].at(-1).t<=.1);assert.ok(result.curves[1][0].t>=.5);
  assert.equal(JSON.stringify(frames),original);
});
test('sparse observations have no curve; missing release has no alignment origin',()=>{
  assert.equal(build([frame(0),frame(.02)],shot).curves.length,0);
  assert.equal(build([frame(0,0,0,'predicted'),frame(.4)],shot).origin,null);
  assert.deepEqual(build([],shot).curves,[]);
});
test('honors corrected release, end and leftward movement',()=>{
  const frames=Array.from({length:50},(_,i)=>frame(i*.02,200-i,30+i*i));
  const result=build(frames,{release_s:.2,end_s:.6});
  assert.equal(result.origin.t,.2);assert.ok(result.points.every(p=>p.t>=.2&&p.t<=.6));
  assert.ok(result.curves[0].at(-1).x<result.curves[0][0].x);
});
