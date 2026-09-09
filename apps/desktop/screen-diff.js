const DEFAULT_DIFF_THRESHOLD = 0.08;
const MIN_DIFF_THRESHOLD = 0.02;
const MAX_DIFF_THRESHOLD = 0.25;
const SAMPLE_WIDTH = 64;
const SAMPLE_HEIGHT = 36;

function clampThreshold(value) {
  const n = Number(value);
  return Number.isFinite(n)
    ? Math.max(MIN_DIFF_THRESHOLD, Math.min(MAX_DIFF_THRESHOLD, n))
    : DEFAULT_DIFF_THRESHOLD;
}

function pixelDifference(previous, current) {
  if (!previous || !current || previous.length !== current.length || previous.length === 0) return 1;

  // Electron nativeImage.toBitmap() is BGRA. Sampling a small grid keeps this
  // local comparison cheap and guarantees raw screenshots never leave the app.
  const pixelCount = Math.floor(previous.length / 4);
  const sourcePixels = pixelCount;
  if (sourcePixels <= 0) return 1;

  const stride = Math.max(1, Math.floor(Math.sqrt(sourcePixels / (SAMPLE_WIDTH * SAMPLE_HEIGHT))));
  let total = 0;
  let samples = 0;
  for (let i = 0; i < pixelCount; i += stride) {
    const offset = i * 4;
    const pb = previous[offset];
    const pg = previous[offset + 1];
    const pr = previous[offset + 2];
    const cb = current[offset];
    const cg = current[offset + 1];
    const cr = current[offset + 2];
    total += (Math.abs(pr - cr) + Math.abs(pg - cg) + Math.abs(pb - cb)) / (255 * 3);
    samples += 1;
  }
  return samples ? total / samples : 1;
}

module.exports = {
  DEFAULT_DIFF_THRESHOLD,
  MIN_DIFF_THRESHOLD,
  MAX_DIFF_THRESHOLD,
  clampThreshold,
  pixelDifference,
};
