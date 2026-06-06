const GEMINI_INPUT_SAMPLE_RATE = 16000;
const GEMINI_OUTPUT_SAMPLE_RATE = 24000;
const GEMINI_INPUT_MIME_TYPE = "audio/pcm;rate=16000";
const GEMINI_AUDIO_WORKLET_NAME = "gemini-pcm-capture";

export type GeminiLiveToken = {
  session_id: string;
  token: string;
  expire_time: string | null;
  new_session_expire_time: string | null;
  model: string;
  api_version: string;
};

export type GeminiTranscriptEvent = {
  role: "user" | "assistant";
  text: string;
  eventId: string;
};

type GeminiLiveCallbacks = {
  onListening: () => void;
  onSpeaking: () => void;
  onTurnComplete: () => void;
  onInterrupted: () => void;
  onTranscript: (event: GeminiTranscriptEvent) => void;
  onNotice: (message: string) => void;
  onError: (error: Error) => void;
};

type GeminiInlineData = {
  mimeType?: string;
  mime_type?: string;
  data?: string;
};

type GeminiPart = {
  inlineData?: GeminiInlineData;
  inline_data?: GeminiInlineData;
  text?: string;
};

type GeminiServerContent = {
  generationComplete?: boolean;
  turnComplete?: boolean;
  interrupted?: boolean;
  inputTranscription?: { text?: string };
  outputTranscription?: { text?: string };
  modelTurn?: {
    parts?: GeminiPart[];
  };
};

type GeminiServerMessage = {
  setupComplete?: object;
  serverContent?: GeminiServerContent;
  error?: { message?: string };
};

type CaptureNode = AudioWorkletNode | ScriptProcessorNode;

function normalizeGeminiModel(model: string) {
  return model.startsWith("models/") ? model : `models/${model}`;
}

function bytesToBase64(bytes: Uint8Array) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    const chunk = bytes.subarray(index, index + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

function base64ToBytes(base64: string) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function resampleLinear(input: Float32Array, sourceRate: number, targetRate: number) {
  if (sourceRate === targetRate) {
    return input;
  }

  const targetLength = Math.max(1, Math.round((input.length * targetRate) / sourceRate));
  const output = new Float32Array(targetLength);
  const ratio = sourceRate / targetRate;

  for (let index = 0; index < targetLength; index += 1) {
    const sourceIndex = index * ratio;
    const before = Math.floor(sourceIndex);
    const after = Math.min(before + 1, input.length - 1);
    const weight = sourceIndex - before;
    output[index] = input[before] * (1 - weight) + input[after] * weight;
  }

  return output;
}

function float32ToPcm16Base64(samples: Float32Array, sourceRate: number) {
  const resampled = resampleLinear(samples, sourceRate, GEMINI_INPUT_SAMPLE_RATE);
  const bytes = new Uint8Array(resampled.length * 2);
  const view = new DataView(bytes.buffer);

  for (let index = 0; index < resampled.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, resampled[index]));
    const value = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    view.setInt16(index * 2, value, true);
  }

  return bytesToBase64(bytes);
}

function pcm16Base64ToFloat32(base64: string) {
  const bytes = base64ToBytes(base64);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const samples = new Float32Array(Math.floor(bytes.byteLength / 2));

  for (let index = 0; index < samples.length; index += 1) {
    samples[index] = view.getInt16(index * 2, true) / 0x8000;
  }

  return samples;
}

function hashText(text: string) {
  let hash = 0;
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 31 + text.charCodeAt(index)) | 0;
  }
  return Math.abs(hash).toString(36);
}

function buildSetupMessage(token: GeminiLiveToken) {
  return {
    setup: {
      model: normalizeGeminiModel(token.model),
      generationConfig: {
        responseModalities: ["AUDIO"],
        temperature: 0.7,
      },
      inputAudioTranscription: {},
      outputAudioTranscription: {},
    },
  };
}

function readInlineData(part: GeminiPart) {
  return part.inlineData ?? part.inline_data ?? null;
}

function isAudioInlineData(inlineData: GeminiInlineData) {
  const mimeType = inlineData.mimeType ?? inlineData.mime_type ?? "";
  return mimeType.startsWith("audio/pcm") && Boolean(inlineData.data);
}

export async function readSocketMessageText(rawData: unknown) {
  if (typeof rawData === "string") {
    return rawData;
  }
  if (rawData instanceof Blob) {
    return rawData.text();
  }
  if (rawData instanceof ArrayBuffer) {
    return new TextDecoder().decode(rawData);
  }
  if (ArrayBuffer.isView(rawData)) {
    return new TextDecoder().decode(rawData);
  }

  throw new Error("Gemini Live returned an unsupported WebSocket message type");
}

function buildGeminiLiveWebsocketUrl(token: GeminiLiveToken) {
  const apiVersion = token.api_version || "v1alpha";
  const method = `google.ai.generativelanguage.${apiVersion}.GenerativeService.BidiGenerateContentConstrained`;
  return `wss://generativelanguage.googleapis.com/ws/${method}?access_token=${encodeURIComponent(token.token)}`;
}

function createCaptureWorkletSource() {
  return `
    class GeminiPcmCapture extends AudioWorkletProcessor {
      constructor() {
        super();
        this.buffer = [];
        this.bufferSize = 4096;
      }

      process(inputs) {
        const channel = inputs[0] && inputs[0][0];
        if (!channel) {
          return true;
        }

        for (let index = 0; index < channel.length; index += 1) {
          this.buffer.push(channel[index]);
        }

        if (this.buffer.length >= this.bufferSize) {
          this.port.postMessage(new Float32Array(this.buffer));
          this.buffer = [];
        }

        return true;
      }
    }

    registerProcessor("${GEMINI_AUDIO_WORKLET_NAME}", GeminiPcmCapture);
  `;
}

class PcmAudioPlayer {
  private nextStartTime = 0;

  constructor(private readonly audioContext: AudioContext) {}

  reset() {
    this.nextStartTime = this.audioContext.currentTime;
  }

  async play(base64: string) {
    await this.audioContext.resume();
    const samples = pcm16Base64ToFloat32(base64);
    if (samples.length === 0) {
      return;
    }

    const buffer = this.audioContext.createBuffer(1, samples.length, GEMINI_OUTPUT_SAMPLE_RATE);
    buffer.copyToChannel(samples, 0);

    const source = this.audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(this.audioContext.destination);

    const startTime = Math.max(this.audioContext.currentTime + 0.02, this.nextStartTime);
    source.start(startTime);
    this.nextStartTime = startTime + buffer.duration;
  }
}

export class GeminiLiveAudioSession {
  private socket: WebSocket | null = null;
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private captureNode: CaptureNode | null = null;
  private silentGain: GainNode | null = null;
  private player: PcmAudioPlayer | null = null;
  private startedCapture = false;
  private closed = false;

  constructor(
    private readonly token: GeminiLiveToken,
    private readonly callbacks: GeminiLiveCallbacks,
  ) {}

  async start() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("当前浏览器不支持麦克风录音");
    }
    if (!window.AudioContext || !window.WebSocket) {
      throw new Error("当前浏览器不支持 Gemini Live 音频链路");
    }

    this.closed = false;
    this.audioContext = new AudioContext();
    this.player = new PcmAudioPlayer(this.audioContext);
    await this.audioContext.resume();

    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });

    await this.openSocket();
  }

  close() {
    this.closed = true;
    this.socket?.close();
    this.socket = null;
    this.captureNode?.disconnect();
    this.captureNode = null;
    this.sourceNode?.disconnect();
    this.sourceNode = null;
    this.silentGain?.disconnect();
    this.silentGain = null;
    this.mediaStream?.getTracks().forEach((track) => track.stop());
    this.mediaStream = null;
    this.player?.reset();
    void this.audioContext?.close();
    this.audioContext = null;
    this.startedCapture = false;
  }

  private async openSocket() {
    const socket = new WebSocket(buildGeminiLiveWebsocketUrl(this.token));
    this.socket = socket;

    socket.onopen = () => {
      socket.send(JSON.stringify(buildSetupMessage(this.token)));
      this.callbacks.onNotice("Gemini Live 已连接，正在初始化音频会话");
    };

    socket.onmessage = (event) => {
      void this.handleSocketMessage(event.data);
    };

    socket.onerror = () => {
      this.callbacks.onError(new Error("Gemini Live WebSocket 连接失败"));
    };

    socket.onclose = () => {
      if (!this.closed) {
        this.callbacks.onTurnComplete();
        this.callbacks.onNotice("Gemini Live 连接已关闭");
      }
    };
  }

  private async startCapture() {
    if (this.startedCapture || !this.audioContext || !this.mediaStream) {
      return;
    }

    this.startedCapture = true;
    this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);
    this.silentGain = this.audioContext.createGain();
    this.silentGain.gain.value = 0;

    if (this.audioContext.audioWorklet) {
      const workletUrl = URL.createObjectURL(
        new Blob([createCaptureWorkletSource()], { type: "text/javascript" }),
      );
      try {
        await this.audioContext.audioWorklet.addModule(workletUrl);
        const workletNode = new AudioWorkletNode(this.audioContext, GEMINI_AUDIO_WORKLET_NAME);
        workletNode.port.onmessage = (message) => {
          this.sendAudioChunk(message.data as Float32Array);
        };
        this.captureNode = workletNode;
        this.sourceNode.connect(workletNode).connect(this.silentGain).connect(this.audioContext.destination);
      } finally {
        URL.revokeObjectURL(workletUrl);
      }
    } else {
      const processor = this.audioContext.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (event) => {
        this.sendAudioChunk(event.inputBuffer.getChannelData(0));
      };
      this.captureNode = processor;
      this.sourceNode.connect(processor).connect(this.silentGain).connect(this.audioContext.destination);
    }

    this.callbacks.onListening();
    this.callbacks.onNotice("Gemini Live 正在聆听你的回答");
  }

  private sendAudioChunk(samples: Float32Array) {
    if (this.closed || !this.socket || !this.audioContext || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }

    const data = float32ToPcm16Base64(samples, this.audioContext.sampleRate);
    this.socket.send(
      JSON.stringify({
        realtimeInput: {
          audio: {
            mimeType: GEMINI_INPUT_MIME_TYPE,
            data,
          },
        },
      }),
    );
  }

  private async handleSocketMessage(rawData: unknown) {
    try {
      const message = JSON.parse(await readSocketMessageText(rawData)) as GeminiServerMessage;

      if (message.error?.message) {
        throw new Error(message.error.message);
      }
      if (message.setupComplete) {
        void this.startCapture();
      }

      const serverContent = message.serverContent;
      if (!serverContent) {
        return;
      }

      if (serverContent.interrupted) {
        this.player?.reset();
        this.callbacks.onInterrupted();
      }
      if (serverContent.inputTranscription?.text) {
        this.emitTranscript("user", serverContent.inputTranscription.text);
      }
      if (serverContent.outputTranscription?.text) {
        this.emitTranscript("assistant", serverContent.outputTranscription.text);
      }

      const parts = serverContent.modelTurn?.parts ?? [];
      for (const part of parts) {
        const inlineData = readInlineData(part);
        if (inlineData && isAudioInlineData(inlineData) && inlineData.data) {
          this.callbacks.onSpeaking();
          void this.player?.play(inlineData.data);
        }
      }

      if (serverContent.generationComplete || serverContent.turnComplete) {
        this.callbacks.onTurnComplete();
      }
    } catch (error) {
      this.callbacks.onError(error instanceof Error ? error : new Error("Gemini Live 消息解析失败"));
    }
  }

  private emitTranscript(role: GeminiTranscriptEvent["role"], rawText: string) {
    const text = rawText.trim();
    if (!text) {
      return;
    }

    this.callbacks.onTranscript({
      role,
      text,
      eventId: `gemini:${role}:${hashText(text)}`,
    });
  }
}
