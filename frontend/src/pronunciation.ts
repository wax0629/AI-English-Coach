export type PronunciationAssessment = {
  session_id: string;
  reference_text: string;
  recognized_text: string;
  scores: {
    pronunciation: number;
    accuracy: number;
    fluency: number;
    completeness: number;
    prosody: number;
  };
  words: Array<{
    word: string;
    accuracy: number;
    error_type: string;
  }>;
  feedback: {
    level: "excellent" | "good" | "needs_focus" | "retry" | "no_speech" | "assessment_unavailable";
    message: string;
  };
};

export function buildPronunciationDiagnostics(assessment: PronunciationAssessment) {
  const recognizedText = assessment.recognized_text.trim() || "未识别到有效英文语音";

  return {
    referenceLabel: `评分句：${assessment.reference_text}`,
    recognizedLabel: `Azure 听到：${recognizedText}`,
  };
}

export type AzureReadyAudio = {
  audioBase64: string;
  contentType: "audio/wav";
};

const targetSampleRate = 16000;

function mixToMono(buffer: AudioBuffer, targetRate: number): Float32Array {
  const outputLength = Math.max(1, Math.floor(buffer.duration * targetRate));
  const output = new Float32Array(outputLength);
  const sourceRate = buffer.sampleRate;
  const channelCount = buffer.numberOfChannels;

  for (let outputIndex = 0; outputIndex < outputLength; outputIndex += 1) {
    const sourceIndex = (outputIndex * sourceRate) / targetRate;
    const lowerIndex = Math.floor(sourceIndex);
    const upperIndex = Math.min(lowerIndex + 1, buffer.length - 1);
    const blend = sourceIndex - lowerIndex;
    let sample = 0;

    for (let channel = 0; channel < channelCount; channel += 1) {
      const data = buffer.getChannelData(channel);
      const lower = data[lowerIndex] ?? 0;
      const upper = data[upperIndex] ?? lower;
      sample += lower + (upper - lower) * blend;
    }

    output[outputIndex] = sample / channelCount;
  }

  return output;
}

function encodePcm16Wav(samples: Float32Array, sampleRate: number): ArrayBuffer {
  const bytesPerSample = 2;
  const blockAlign = bytesPerSample;
  const buffer = new ArrayBuffer(44 + samples.length * bytesPerSample);
  const view = new DataView(buffer);

  function writeString(offset: number, value: string) {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  }

  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * bytesPerSample, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, samples.length * bytesPerSample, true);

  let offset = 44;
  for (const sample of samples) {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += bytesPerSample;
  }

  return buffer;
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";

  for (let index = 0; index < bytes.length; index += chunkSize) {
    const chunk = bytes.subarray(index, index + chunkSize);
    binary += String.fromCharCode(...chunk);
  }

  return window.btoa(binary);
}

export async function convertRecordingToAzureWav(blob: Blob): Promise<AzureReadyAudio> {
  const audioContext = new AudioContext();
  try {
    const sourceBuffer = await blob.arrayBuffer();
    const decoded = await audioContext.decodeAudioData(sourceBuffer.slice(0));
    const monoSamples = mixToMono(decoded, targetSampleRate);
    const wavBuffer = encodePcm16Wav(monoSamples, targetSampleRate);

    return {
      audioBase64: arrayBufferToBase64(wavBuffer),
      contentType: "audio/wav",
    };
  } finally {
    await audioContext.close();
  }
}
