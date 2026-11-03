// Renderer regression checks: no browser or camera/microphone access.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function renderer(hidden = false) {
  const queue = [], rectangles = [];
  const context = {
    fillRect(...args) { rectangles.push({args, color: this.fillStyle}); },
    save() {}, restore() {}, translate() {}, scale() {}, clearRect() {},
  };
  const scope = {
    document: {hidden, getElementById: () => ({getContext: () => context})},
    matchMedia: () => ({matches: false}),
    performance: {now: () => 1000},
    requestAnimationFrame: fn => queue.push(fn), window: {}, Math,
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../governor/static/face.js'), 'utf8'), scope);
  return {scope, queue, rectangles};
}

test('background tabs still receive an initial face and forced state updates', () => {
  const r = renderer(true);
  assert.ok(r.rectangles.length > 2, 'face must not be blank on initial background load');
  r.rectangles.length = 0;
  r.scope.window.governorFace.setState({status: 'idle', emotion: 'happy', display: {palette: 'amber', inset: .04}});
  assert.ok(r.rectangles.some(rect => rect.color === '#ffcb75'));
  assert.equal(r.queue.length, 1, 'state updates must not create duplicate animation loops');
});

test('normal animation does not render more than 30 frames per second', () => {
  const r = renderer();
  r.rectangles.length = 0;
  r.queue.shift()(1010);
  assert.equal(r.rectangles.length, 0);
  r.queue.shift()(1040);
  assert.ok(r.rectangles.length > 2);
  assert.equal(r.queue.length, 1);
});

test('background animation stops drawing between state updates', () => {
  const r = renderer(true);
  r.rectangles.length = 0;
  r.queue.shift()(5000);
  assert.equal(r.rectangles.length, 0);
});
