const assert = require('assert');
const {
  clampThreshold,
  pixelDifference,
  DEFAULT_DIFF_THRESHOLD,
  MIN_DIFF_THRESHOLD,
  MAX_DIFF_THRESHOLD,
} = require('./screen-diff');

assert.strictEqual(pixelDifference(null, null), 1);
assert.strictEqual(pixelDifference(Buffer.from([0, 0, 0, 255]), Buffer.from([0, 0, 0, 255])), 0);
assert(pixelDifference(Buffer.from([0, 0, 0, 255]), Buffer.from([255, 255, 255, 255])) > 0.99);
assert.strictEqual(pixelDifference(Buffer.from([0, 0, 0, 255]), Buffer.from([0, 0, 0])), 1);
assert.strictEqual(clampThreshold(-1), MIN_DIFF_THRESHOLD);
assert.strictEqual(clampThreshold(1), MAX_DIFF_THRESHOLD);
assert.strictEqual(clampThreshold('bad'), DEFAULT_DIFF_THRESHOLD);
console.log('screen-diff tests passed');
