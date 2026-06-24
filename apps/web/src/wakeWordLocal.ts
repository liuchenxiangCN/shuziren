/**
 * 本地唤醒词匹配模块
 *
 * 方案: MFCC 音频特征提取 + DTW (动态时间规整) 本地比对
 * - 完全在浏览器端计算, 无网络往返
 * - 预先用 TTS 生成唤醒词模板音频, 提取 MFCC 特征后存储
 * - 实时 VAD 截取的音频片段提取 MFCC 后与模板做 DTW 比对
 * - 低于阈值即为命中, 延迟 ~50-100ms
 */

// ---------------------------------------------------------------------------
// FFT (radix-2 Cooley-Tukey, in-place)
// ---------------------------------------------------------------------------

function nextPowerOfTwo(n: number): number {
  let p = 1;
  while (p < n) p <<= 1;
  return p;
}

function fft(re: Float64Array, im: Float64Array): void {
  const n = re.length;
  if (n <= 1) return;

  // Bit-reversal permutation
  for (let i = 0, j = 0; i < n; i++) {
    if (j > i) {
      let t = re[i]; re[i] = re[j]; re[j] = t;
      t = im[i]; im[i] = im[j]; im[j] = t;
    }
    let m = n >> 1;
    while (m >= 1 && j >= m) {
      j -= m;
      m >>= 1;
    }
    j += m;
  }

  // Cooley-Tukey butterfly
  for (let size = 2; size <= n; size <<= 1) {
    const halfSize = size >> 1;
    const angle = (-2 * Math.PI) / size;
    for (let i = 0; i < n; i += size) {
      for (let j = 0; j < halfSize; j++) {
        const a = angle * j;
        const cos = Math.cos(a);
        const sin = Math.sin(a);
        const tre = cos * re[i + j + halfSize] - sin * im[i + j + halfSize];
        const tim = cos * im[i + j + halfSize] + sin * re[i + j + halfSize];
        re[i + j + halfSize] = re[i + j] - tre;
        im[i + j + halfSize] = im[i + j] - tim;
        re[i + j] += tre;
        im[i + j] += tim;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Mel filterbank
// ---------------------------------------------------------------------------

function hzToMel(hz: number): number {
  return 2595 * Math.log10(1 + hz / 700);
}

function melToHz(mel: number): number {
  return 700 * (Math.pow(10, mel / 2595) - 1);
}

function buildMelFilterbank(
  numFilters: number,
  fftSize: number,
  sampleRate: number,
  lowFreq: number,
  highFreq: number,
): Float64Array[] {
  const numBins = Math.floor(fftSize / 2) + 1;
  const lowMel = hzToMel(lowFreq);
  const highMel = hzToMel(highFreq);
  const melPoints = new Float64Array(numFilters + 2);
  for (let i = 0; i < numFilters + 2; i++) {
    melPoints[i] = melToHz(lowMel + (i * (highMel - lowMel)) / (numFilters + 1));
  }

  const bins = new Float64Array(numFilters + 2);
  for (let i = 0; i < numFilters + 2; i++) {
    bins[i] = Math.floor(((fftSize + 1) * melPoints[i]) / sampleRate);
  }

  const filters: Float64Array[] = [];
  for (let m = 1; m <= numFilters; m++) {
    const filter = new Float64Array(numBins);
    for (let k = Math.floor(bins[m - 1]); k < Math.floor(bins[m]); k++) {
      filter[k] = (k - bins[m - 1]) / (bins[m] - bins[m - 1]);
    }
    for (let k = Math.floor(bins[m]); k < Math.floor(bins[m + 1]); k++) {
      filter[k] = (bins[m + 1] - k) / (bins[m + 1] - bins[m]);
    }
    filters.push(filter);
  }
  return filters;
}

// ---------------------------------------------------------------------------
// MFCC extraction
// ---------------------------------------------------------------------------

interface MfccConfig {
  sampleRate: number;
  numCoeffs: number;
  numFilters: number;
  frameLenMs: number;
  frameStrideMs: number;
  lowFreq: number;
  highFreq: number;
  preEmphasisAlpha: number;
}

const DEFAULT_MFCC_CONFIG: MfccConfig = {
  sampleRate: 16000,
  numCoeffs: 13,
  numFilters: 26,
  frameLenMs: 25,
  frameStrideMs: 10,
  lowFreq: 20,
  highFreq: 8000,
  preEmphasisAlpha: 0.97,
};

/** MFCC feature vectors — each frame produces one Float64Array of numCoeffs length */
export type MfccFeatures = Float64Array[];

/**
 * Extract MFCC features from raw PCM samples (mono, 16-bit/sample in Float32Array [-1, 1]).
 * Returns one MFCC vector per frame.
 */
export function extractMfcc(
  samples: Float32Array,
  config: Partial<MfccConfig> = {},
): MfccFeatures {
  const cfg = { ...DEFAULT_MFCC_CONFIG, ...config };
  const {
    sampleRate, numCoeffs, numFilters,
    frameLenMs, frameStrideMs, lowFreq, highFreq, preEmphasisAlpha,
  } = cfg;

  // 1. Pre-emphasis
  const emphasized = new Float32Array(samples.length);
  emphasized[0] = samples[0];
  for (let i = 1; i < samples.length; i++) {
    emphasized[i] = samples[i] - preEmphasisAlpha * samples[i - 1];
  }

  // 2. Frame parameters
  const frameLen = Math.floor(sampleRate * frameLenMs / 1000);
  const frameStride = Math.floor(sampleRate * frameStrideMs / 1000);
  const numFrames = Math.max(1, Math.floor((emphasized.length - frameLen) / frameStride) + 1);
  const fftSize = nextPowerOfTwo(frameLen);

  // 3. Hamming window
  const hamming = new Float64Array(frameLen);
  for (let i = 0; i < frameLen; i++) {
    hamming[i] = 0.54 - 0.46 * Math.cos((2 * Math.PI * i) / (frameLen - 1));
  }

  // 4. Mel filterbank (cached by dimensionality)
  const filters = buildMelFilterbank(numFilters, fftSize, sampleRate, lowFreq, highFreq);

  // 5. Process each frame
  const features: MfccFeatures = [];
  for (let f = 0; f < numFrames; f++) {
    const offset = f * frameStride;

    // Windowed frame → FFT real/imag arrays
    const re = new Float64Array(fftSize);
    const im = new Float64Array(fftSize);
    for (let i = 0; i < frameLen; i++) {
      re[i] = emphasized[offset + i] * hamming[i];
    }

    fft(re, im);

    // Power spectrum
    const powerSpec = new Float64Array(fftSize / 2 + 1);
    for (let i = 0; i < powerSpec.length; i++) {
      powerSpec[i] = (re[i] * re[i] + im[i] * im[i]) / fftSize;
    }

    // Mel filterbank energies
    const melEnergies = new Float64Array(numFilters);
    for (let m = 0; m < numFilters; m++) {
      let energy = 0;
      const filter = filters[m];
      for (let k = 0; k < powerSpec.length; k++) {
        energy += powerSpec[k] * filter[k];
      }
      // Avoid log(0)
      melEnergies[m] = Math.log(Math.max(energy, 1e-12));
    }

    // DCT type-II → MFCC
    const mfcc = new Float64Array(numCoeffs);
    for (let k = 0; k < numCoeffs; k++) {
      let sum = 0;
      for (let n = 0; n < numFilters; n++) {
        sum += melEnergies[n] * Math.cos((Math.PI * k * (n + 0.5)) / numFilters);
      }
      mfcc[k] = sum;
    }

    // Cepstral mean normalization (subtract per-frame mean to reduce channel effects)
    let mean = 0;
    for (let i = 0; i < numCoeffs; i++) mean += mfcc[i];
    mean /= numCoeffs;
    for (let i = 0; i < numCoeffs; i++) mfcc[i] -= mean;

    features.push(mfcc);
  }

  return features;
}

// ---------------------------------------------------------------------------
// DTW (Dynamic Time Warping)
// ---------------------------------------------------------------------------

function euclideanDistance(a: Float64Array, b: Float64Array): number {
  let sum = 0;
  for (let i = 0; i < a.length; i++) {
    const d = a[i] - b[i];
    sum += d * d;
  }
  return Math.sqrt(sum);
}

/**
 * Compute normalized DTW distance between two MFCC feature sequences.
 * Lower = more similar. Use Sakoe-Chiba band constraint for speed.
 */
export function dtwDistance(
  a: MfccFeatures,
  b: MfccFeatures,
  bandwidthRatio = 0.2,
): number {
  const n = a.length;
  const m = b.length;
  if (n === 0 || m === 0) return Infinity;

  const bandwidth = Math.max(Math.abs(n - m), Math.floor(Math.max(n, m) * bandwidthRatio));
  const dtw = new Float64Array((n + 1) * (m + 1));
  const INF = 1e308;

  // Initialize
  for (let i = 0; i <= n; i++) {
    for (let j = 0; j <= m; j++) {
      dtw[i * (m + 1) + j] = INF;
    }
  }
  dtw[0] = 0;

  for (let i = 1; i <= n; i++) {
    const jMin = Math.max(1, i - bandwidth);
    const jMax = Math.min(m, i + bandwidth);
    for (let j = jMin; j <= jMax; j++) {
      const cost = euclideanDistance(a[i - 1], b[j - 1]);
      const prev = Math.min(
        dtw[(i - 1) * (m + 1) + j],       // insertion
        dtw[i * (m + 1) + (j - 1)],       // deletion
        dtw[(i - 1) * (m + 1) + (j - 1)], // match
      );
      dtw[i * (m + 1) + j] = cost + prev;
    }
  }

  return dtw[n * (m + 1) + m] / (n + m);
}

// ---------------------------------------------------------------------------
// Wake word template management
// ---------------------------------------------------------------------------

export interface WakeWordTemplate {
  word: string;
  features: MfccFeatures;
}

/**
 * Load a wake word audio file from URL, decode it, and extract MFCC features.
 */
export async function loadWakeWordTemplate(
  word: string,
  url: string,
): Promise<WakeWordTemplate> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to fetch wake word template: ${url}`);
  const arrayBuffer = await response.arrayBuffer();
  const audioContext = new AudioContext({ sampleRate: DEFAULT_MFCC_CONFIG.sampleRate });
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
  await audioContext.close();

  // Resample to 16kHz mono if needed, then extract MFCC
  const samples = resampleTo16kMono(audioBuffer);
  const features = extractMfcc(samples);
  return { word, features };
}

/**
 * Simple resampling + mono mix for decoded AudioBuffer → 16kHz Float32Array
 */
function resampleTo16kMono(buffer: AudioBuffer): Float32Array {
  const targetRate = DEFAULT_MFCC_CONFIG.sampleRate;
  const numChannels = buffer.numberOfChannels;
  const srcRate = buffer.sampleRate;
  const srcLength = buffer.length;
  const targetLength = Math.floor(srcLength * targetRate / srcRate);
  const result = new Float32Array(targetLength);

  for (let i = 0; i < targetLength; i++) {
    const srcIdx = i * srcRate / targetRate;
    const srcIdxFloor = Math.floor(srcIdx);
    const srcIdxCeil = Math.min(srcIdxFloor + 1, srcLength - 1);
    const frac = srcIdx - srcIdxFloor;

    let sample = 0;
    for (let ch = 0; ch < numChannels; ch++) {
      const chData = buffer.getChannelData(ch);
      sample += chData[srcIdxFloor] * (1 - frac) + chData[srcIdxCeil] * frac;
    }
    result[i] = sample / numChannels;
  }
  return result;
}

// ---------------------------------------------------------------------------
// Matching
// ---------------------------------------------------------------------------

export interface MatchResult {
  matched: boolean;
  word: string | null;
  distance: number;
  threshold: number;
}

/**
 * Match a recorded audio segment against pre-loaded wake word templates.
 * Returns the best match if its DTW distance falls below the threshold.
 *
 * @param samples - Raw PCM audio samples (Float32Array, mono, 16kHz)
 * @param templates - Pre-loaded wake word templates
 * @param threshold - DTW distance threshold (lower = stricter). Default 1.8.
 *                    Tune based on testing: 1.5 = strict, 2.0 = loose.
 */
export function matchWakeWord(
  samples: Float32Array,
  templates: WakeWordTemplate[],
  threshold = 1.8,
): MatchResult {
  if (templates.length === 0) return { matched: false, word: null, distance: Infinity, threshold };

  const inputFeatures = extractMfcc(samples);
  if (inputFeatures.length < 3) return { matched: false, word: null, distance: Infinity, threshold };

  let bestWord: string | null = null;
  let bestDistance = Infinity;

  for (const tpl of templates) {
    const dist = dtwDistance(inputFeatures, tpl.features);
    if (dist < bestDistance) {
      bestDistance = dist;
      bestWord = tpl.word;
    }
  }

  return {
    matched: bestDistance < threshold,
    word: bestWord,
    distance: bestDistance,
    threshold,
  };
}

/**
 * Convert raw PCM Int16 bytes to Float32Array [-1, 1] at 16kHz mono.
 */
export function pcmBytesToFloat32(bytes: ArrayBuffer): Float32Array {
  const view = new DataView(bytes);
  const numSamples = Math.floor(bytes.byteLength / 2);
  const result = new Float32Array(numSamples);
  for (let i = 0; i < numSamples; i++) {
    result[i] = view.getInt16(i * 2, true) / 32768;
  }
  return result;
}
