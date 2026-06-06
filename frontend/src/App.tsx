import {
  AlertCircle,
  ArrowLeft,
  BriefcaseBusiness,
  Check,
  CheckCircle2,
  CircleStop,
  Coffee,
  Flame,
  Headphones,
  Loader2,
  Mic,
  Mic2,
  Play,
  Presentation,
  Radio,
  Route,
  ShieldCheck,
  Sparkles,
  Star,
  Target,
  Trophy,
  Volume2,
  Waves,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { CSSProperties } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { GeminiLiveAudioSession, type GeminiLiveToken, type GeminiTranscriptEvent } from "./gemini-live";
import "./styles.css";

type Difficulty = "a2" | "b1" | "b2";
type AppView = "map" | "room" | "report";
type VoiceProvider = "openai" | "gemini";
type RealtimeStatus = "idle" | "connecting" | "ready" | "listening" | "speaking" | "ended" | "error";
type ReportLevel = "standard" | "advanced";

type Scenario = {
  id: string;
  title: string;
  subtitle: string;
  role: string;
  user_goal: string;
  default_difficulty: Difficulty;
  target_expressions: string[];
  accent_color: string;
};

type CreatedSession = {
  session_id: string;
  scenario: Scenario;
  difficulty: Difficulty;
  status: "active" | "finished";
};

type ConversationRole = "user" | "assistant";

type ConversationTurn = {
  turn_id: string;
  session_id: string;
  role: ConversationRole;
  text: string;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
};

type PracticeReport = {
  report_id: string;
  session_id: string;
  scenario_id: string;
  difficulty: Difficulty;
  generated_at: string;
  summary: string;
  scores: {
    overall: number;
    fluency: number;
    grammar: number;
    vocabulary: number;
    goal_completion: number;
  };
  metrics: {
    report_level: ReportLevel;
    total_turns: number;
    user_turns: number;
    assistant_turns: number;
    word_count: number;
    average_words_per_user_turn: number;
    target_expression_hits: string[];
    missed_target_expressions: string[];
    generation_mode: "rules" | "llm";
    llm_provider: "rules" | "gemini" | "deepseek";
    llm_model: string | null;
    llm_error: string | null;
  };
  badges: string[];
  strengths: string[];
  corrections: Array<{
    original: string;
    suggestion: string;
    reason: string;
    severity: "low" | "medium" | "high";
  }>;
  drills: Array<{
    title: string;
    prompt: string;
    target_expression: string;
  }>;
};

type RealtimeClientSecret = {
  session_id: string;
  realtime_session_id: string | null;
  client_secret: string;
  expires_at: number | null;
  model: string;
  voice: string;
};

type RealtimeEvent = {
  type?: string;
  transcript?: string;
  text?: string;
  delta?: string;
  item_id?: string;
  response_id?: string;
  error?: { message?: string };
};

type ScenarioMeta = {
  chapter: string;
  district: string;
  xp: number;
  reward: string;
  time: string;
  checkpoint: string;
  signal: string;
};

type AccentStyle = CSSProperties & { "--accent": string };

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const scoreLabels: Array<{ key: keyof PracticeReport["scores"]; label: string; caption: string }> = [
  { key: "fluency", label: "流利度", caption: "节奏与连续表达" },
  { key: "grammar", label: "语法", caption: "句式稳定性" },
  { key: "vocabulary", label: "词汇", caption: "场景表达丰富度" },
  { key: "goal_completion", label: "目标", caption: "任务完成度" },
];

const difficultyOptions: Array<{ id: Difficulty; label: string; description: string }> = [
  { id: "a2", label: "轻松开口", description: "短句应答" },
  { id: "b1", label: "稳定表达", description: "完整回答" },
  { id: "b2", label: "进阶追问", description: "观点展开" },
];

const scenarioIcons: Record<string, LucideIcon> = {
  interview: BriefcaseBusiness,
  restaurant: Coffee,
  meeting: Presentation,
};

const scenarioMeta: Record<string, ScenarioMeta> = {
  interview: {
    chapter: "Level 01",
    district: "Career Gate",
    xp: 120,
    reward: "面试表达徽章",
    time: "6 min",
    checkpoint: "讲出 1 个 STAR 故事",
    signal: "STAR 追问",
  },
  restaurant: {
    chapter: "Level 02",
    district: "Street Counter",
    xp: 80,
    reward: "自然点餐徽章",
    time: "4 min",
    checkpoint: "完成点餐和改需求",
    signal: "礼貌改口",
  },
  meeting: {
    chapter: "Level 03",
    district: "Board Room",
    xp: 150,
    reward: "会议发言徽章",
    time: "7 min",
    checkpoint: "表达观点并回应追问",
    signal: "观点防守",
  },
};

const realtimeStatusLabels: Record<RealtimeStatus, { label: string; hint: string }> = {
  idle: { label: "待连接", hint: "VOICE IDLE" },
  connecting: { label: "连接中", hint: "SYNCING" },
  ready: { label: "Token 就绪", hint: "GEMINI READY" },
  listening: { label: "聆听中", hint: "LISTENING" },
  speaking: { label: "AI 回复中", hint: "COACH LIVE" },
  ended: { label: "已结束", hint: "SESSION SAVED" },
  error: { label: "连接错误", hint: "CHECK LINK" },
};

const voiceProviderOptions: Array<{ id: VoiceProvider; label: string; caption: string }> = [
  { id: "openai", label: "OpenAI Realtime", caption: "WebRTC 语音" },
  { id: "gemini", label: "Gemini Live", caption: "WebSocket 音频" },
];

// Keep scene dressing in CSS so live voice checks never wait on large images.
function ScenarioBackdrop({ scenarioId }: { scenarioId: string }) {
  if (scenarioId === "restaurant") {
    return (
      <div className="scenario-backdrop restaurant-backdrop" aria-hidden="true">
        <span className="awning" />
        <span className="menu-board board-one" />
        <span className="menu-board board-two" />
        <span className="pendant pendant-one" />
        <span className="pendant pendant-two" />
        <span className="counter-line" />
      </div>
    );
  }

  if (scenarioId === "interview") {
    return (
      <div className="scenario-backdrop interview-backdrop" aria-hidden="true">
        <span className="office-window" />
        <span className="wall-frame" />
        <span className="desk-surface" />
        <span className="candidate-card card-one" />
        <span className="candidate-card card-two" />
        <span className="desk-lamp" />
        <span className="plant-mark" />
      </div>
    );
  }

  if (scenarioId === "meeting") {
    return (
      <div className="scenario-backdrop meeting-backdrop" aria-hidden="true">
        <span className="screen-wall" />
        <span className="screen-chart" />
        <span className="agenda-strip strip-one" />
        <span className="agenda-strip strip-two" />
        <span className="agenda-strip strip-three" />
        <span className="conference-table" />
        <span className="meeting-chair chair-one" />
        <span className="meeting-chair chair-two" />
        <span className="meeting-chair chair-three" />
      </div>
    );
  }

  return null;
}

function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("");
  const [difficulty, setDifficulty] = useState<Difficulty>("b1");
  const [view, setView] = useState<AppView>("map");
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isConnectingRealtime, setIsConnectingRealtime] = useState(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [error, setError] = useState<string>("");
  const [roomError, setRoomError] = useState<string>("");
  const [reportError, setReportError] = useState<string>("");
  const [roomNotice, setRoomNotice] = useState<string>("副本已锁定，等待语音链路启动");
  const [createdSession, setCreatedSession] = useState<CreatedSession | null>(null);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [practiceReport, setPracticeReport] = useState<PracticeReport | null>(null);
  const [realtimeStatus, setRealtimeStatus] = useState<RealtimeStatus>("idle");
  const [voiceProvider, setVoiceProvider] = useState<VoiceProvider>("openai");

  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);
  const geminiSessionRef = useRef<GeminiLiveAudioSession | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  const savedEventIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    let ignore = false;

    async function loadScenarios() {
      try {
        setIsLoading(true);
        setError("");
        const response = await fetch(`${apiBaseUrl}/api/scenarios`);
        if (!response.ok) {
          throw new Error("场景加载失败");
        }
        const data = (await response.json()) as Scenario[];
        if (ignore) {
          return;
        }
        setScenarios(data);
        const first = data[0];
        if (first) {
          setSelectedScenarioId(first.id);
          setDifficulty(first.default_difficulty);
        }
      } catch (loadError) {
        if (!ignore) {
          setError(loadError instanceof Error ? loadError.message : "场景加载失败");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    loadScenarios();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      closeRealtimeConnection("ended");
    };
  }, []);

  useEffect(() => {
    if (!createdSession || view !== "room") {
      return;
    }

    let ignore = false;
    const sessionId = createdSession.session_id;

    async function loadTurns() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/sessions/${sessionId}/turns`);
        if (!response.ok) {
          return;
        }
        const data = (await response.json()) as ConversationTurn[];
        if (!ignore) {
          setTurns(data);
        }
      } catch {
        if (!ignore) {
          setRoomNotice("转写记录稍后同步");
        }
      }
    }

    loadTurns();
    return () => {
      ignore = true;
    };
  }, [createdSession, view]);

  const selectedScenario = useMemo(
    () => scenarios.find((scenario) => scenario.id === selectedScenarioId) ?? null,
    [scenarios, selectedScenarioId],
  );
  const selectedMeta = selectedScenario ? scenarioMeta[selectedScenario.id] : null;
  const activeScenario = createdSession?.scenario ?? selectedScenario;
  const activeMeta = activeScenario ? scenarioMeta[activeScenario.id] : null;
  const statusMeta = realtimeStatusLabels[realtimeStatus];
  const userTurnCount = turns.filter((turn) => turn.role === "user").length;

  function selectScenario(scenario: Scenario) {
    setSelectedScenarioId(scenario.id);
    setDifficulty(scenario.default_difficulty);
    setCreatedSession(null);
    setTurns([]);
    setPracticeReport(null);
    setError("");
    setReportError("");
  }

  function closeRealtimeConnection(nextStatus: RealtimeStatus) {
    dataChannelRef.current?.close();
    dataChannelRef.current = null;
    geminiSessionRef.current?.close();
    geminiSessionRef.current = null;
    peerConnectionRef.current?.close();
    peerConnectionRef.current = null;
    localStreamRef.current?.getTracks().forEach((track) => track.stop());
    localStreamRef.current = null;
    if (remoteAudioRef.current) {
      remoteAudioRef.current.srcObject = null;
    }
    setIsConnectingRealtime(false);
    setRealtimeStatus(nextStatus);
  }

  async function createSession() {
    if (!selectedScenario) {
      return;
    }

    try {
      setIsCreating(true);
      setError("");
      setRoomError("");
      const response = await fetch(`${apiBaseUrl}/api/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario_id: selectedScenario.id,
          difficulty,
          user_id: "demo",
        }),
      });
      if (!response.ok) {
        throw new Error("Session 创建失败");
      }
      const data = (await response.json()) as CreatedSession;
      savedEventIdsRef.current.clear();
      setCreatedSession(data);
      setTurns([]);
      setPracticeReport(null);
      setRealtimeStatus("idle");
      setRoomNotice("副本已锁定，等待语音链路启动");
      setView("room");
      window.requestAnimationFrame(() => {
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Session 创建失败");
    } finally {
      setIsCreating(false);
    }
  }

  async function saveConversationTurn(role: ConversationRole, text: string, eventId: string) {
    if (!createdSession) {
      return;
    }
    const cleanedText = text.trim();
    if (!cleanedText || savedEventIdsRef.current.has(eventId)) {
      return;
    }
    savedEventIdsRef.current.add(eventId);

    try {
      const response = await fetch(`${apiBaseUrl}/api/conversation/turns`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: createdSession.session_id,
          role,
          text: cleanedText,
        }),
      });
      if (!response.ok) {
        throw new Error("转写保存失败");
      }
      const savedTurn = (await response.json()) as ConversationTurn;
      setTurns((currentTurns) => [...currentTurns, savedTurn]);
      setRoomNotice("转写已保存");
    } catch (saveError) {
      setRoomError(saveError instanceof Error ? saveError.message : "转写保存失败");
    }
  }

  function readRealtimeTranscript(event: RealtimeEvent) {
    return event.transcript ?? event.text ?? "";
  }

  function handleRealtimeEvent(event: RealtimeEvent) {
    const eventType = event.type ?? "";

    if (eventType === "input_audio_buffer.speech_started") {
      setRealtimeStatus("listening");
      setRoomNotice("正在聆听你的回答");
    }
    if (eventType === "response.created" || eventType === "response.audio.delta") {
      setRealtimeStatus("speaking");
      setRoomNotice("AI 教练正在回复");
    }
    if (eventType === "response.done") {
      setRealtimeStatus("listening");
      setRoomNotice("轮到你继续表达");
    }
    if (eventType === "error") {
      setRealtimeStatus("error");
      setRoomError(event.error?.message ?? "Realtime 连接出现错误");
    }

    if (eventType === "conversation.item.input_audio_transcription.completed") {
      const eventId = event.item_id ?? `${eventType}:${Date.now()}`;
      void saveConversationTurn("user", readRealtimeTranscript(event), eventId);
    }
    if (eventType === "response.audio_transcript.done" || eventType === "response.output_audio_transcript.done") {
      const eventId = event.response_id ?? event.item_id ?? `${eventType}:${Date.now()}`;
      void saveConversationTurn("assistant", readRealtimeTranscript(event), eventId);
    }
  }

  async function startRealtimeConversation() {
    if (!createdSession || !activeScenario) {
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setRealtimeStatus("error");
      setRoomError("当前浏览器不支持麦克风录音");
      return;
    }

    try {
      closeRealtimeConnection("connecting");
      setIsConnectingRealtime(true);
      setRoomError("");
      setRoomNotice("正在创建安全语音链路");

      const secretResponse = await fetch(`${apiBaseUrl}/api/realtime/client-secret`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: createdSession.session_id }),
      });
      if (!secretResponse.ok) {
        const payload = (await secretResponse.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "Realtime client secret 创建失败");
      }
      const realtime = (await secretResponse.json()) as RealtimeClientSecret;

      const peerConnection = new RTCPeerConnection();
      peerConnectionRef.current = peerConnection;

      peerConnection.ontrack = (event) => {
        if (remoteAudioRef.current) {
          remoteAudioRef.current.srcObject = event.streams[0];
        }
      };
      peerConnection.onconnectionstatechange = () => {
        if (peerConnection.connectionState === "connected") {
          setRealtimeStatus("listening");
          setRoomNotice("语音链路已连接");
        }
        if (peerConnection.connectionState === "failed" || peerConnection.connectionState === "disconnected") {
          setRealtimeStatus("error");
          setRoomError("语音链路已断开");
        }
      };

      const localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
        },
        video: false,
      });
      localStreamRef.current = localStream;
      localStream.getAudioTracks().forEach((track) => {
        peerConnection.addTrack(track, localStream);
      });

      const dataChannel = peerConnection.createDataChannel("oai-events");
      dataChannelRef.current = dataChannel;
      dataChannel.onmessage = (message) => {
        try {
          handleRealtimeEvent(JSON.parse(String(message.data)) as RealtimeEvent);
        } catch {
          setRoomNotice("收到一条语音事件");
        }
      };
      dataChannel.onopen = () => {
        setRealtimeStatus("listening");
        setRoomNotice("语音链路已连接");
        dataChannel.send(
          JSON.stringify({
            type: "response.create",
            response: {
              instructions: `Start the ${activeScenario.title} role-play with one short natural greeting.`,
            },
          }),
        );
      };

      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);

      const sdpResponse = await fetch("https://api.openai.com/v1/realtime/calls", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${realtime.client_secret}`,
          "Content-Type": "application/sdp",
        },
        body: offer.sdp,
      });
      if (!sdpResponse.ok) {
        throw new Error("OpenAI Realtime WebRTC 连接失败");
      }

      await peerConnection.setRemoteDescription({
        type: "answer",
        sdp: await sdpResponse.text(),
      });
    } catch (connectError) {
      closeRealtimeConnection("error");
      setRoomError(connectError instanceof Error ? connectError.message : "Realtime 连接失败");
    } finally {
      setIsConnectingRealtime(false);
    }
  }

  function handleGeminiTranscript(event: GeminiTranscriptEvent) {
    void saveConversationTurn(event.role, event.text, event.eventId);
  }

  async function startGeminiLiveConversation() {
    if (!createdSession) {
      return;
    }

    try {
      closeRealtimeConnection("connecting");
      setIsConnectingRealtime(true);
      setRoomError("");
      setRoomNotice("正在向后端申请 Gemini Live 临时 token");

      const tokenResponse = await fetch(`${apiBaseUrl}/api/gemini/live-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: createdSession.session_id }),
      });
      if (!tokenResponse.ok) {
        const payload = (await tokenResponse.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "Gemini Live token 创建失败");
      }
      const gemini = (await tokenResponse.json()) as GeminiLiveToken;
      setRoomNotice(`Gemini Live token 已就绪：${gemini.model}，正在打开音频流`);

      const liveSession = new GeminiLiveAudioSession(gemini, {
        onListening: () => {
          setRealtimeStatus("listening");
        },
        onSpeaking: () => {
          setRealtimeStatus("speaking");
          setRoomNotice("Gemini Coach 正在回复");
        },
        onTurnComplete: () => {
          setRealtimeStatus("listening");
          setRoomNotice("轮到你继续表达");
        },
        onInterrupted: () => {
          setRealtimeStatus("listening");
          setRoomNotice("已检测到插话，Gemini 正在重新聆听");
        },
        onTranscript: handleGeminiTranscript,
        onNotice: setRoomNotice,
        onError: (liveError) => {
          closeRealtimeConnection("error");
          setRoomError(liveError.message);
          setRoomNotice("Gemini Live 暂不可用，可以切回 OpenAI Realtime 继续演示");
        },
      });
      geminiSessionRef.current = liveSession;
      await liveSession.start();
    } catch (connectError) {
      closeRealtimeConnection("error");
      setRoomError(connectError instanceof Error ? connectError.message : "Gemini Live 音频连接失败");
      setRoomNotice("Gemini Live 暂不可用，可以切回 OpenAI Realtime 继续演示");
    } finally {
      setIsConnectingRealtime(false);
    }
  }

  function startSelectedVoiceProvider() {
    if (voiceProvider === "gemini") {
      void startGeminiLiveConversation();
      return;
    }
    void startRealtimeConversation();
  }

  async function generateReport(reportLevel: ReportLevel) {
    if (!createdSession) {
      return;
    }

    try {
      closeRealtimeConnection("ended");
      setIsGeneratingReport(true);
      setReportError("");
      setRoomError("");
      setRoomNotice(reportLevel === "advanced" ? "正在生成进阶报告，DeepSeek Pro 会更仔细地批改" : "正在生成标准报告");

      const response = await fetch(`${apiBaseUrl}/api/sessions/${createdSession.session_id}/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report_level: reportLevel }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "报告生成失败");
      }

      const report = (await response.json()) as PracticeReport;
      setPracticeReport(report);
      setView("report");
      window.requestAnimationFrame(() => {
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    } catch (reportErrorValue) {
      const message = reportErrorValue instanceof Error ? reportErrorValue.message : "报告生成失败";
      setReportError(message);
      setRoomError(message);
    } finally {
      setIsGeneratingReport(false);
    }
  }

  function returnToMap() {
    closeRealtimeConnection("ended");
    setView("map");
    setRoomError("");
  }

  function returnToRoom() {
    setView("room");
    setReportError("");
  }

  if (view === "report" && createdSession && activeScenario && practiceReport) {
    const reportMeta = scenarioMeta[activeScenario.id];
    const scoreItems = scoreLabels.map((score) => ({
      ...score,
      value: practiceReport.scores[score.key],
    }));
    const generatedBy =
      practiceReport.metrics.generation_mode === "llm"
        ? `${practiceReport.metrics.llm_provider} · ${practiceReport.metrics.llm_model}`
        : "Rules fallback";

    return (
      <main className="report-shell">
        <header className="report-hero">
          <button className="icon-button" onClick={returnToRoom} type="button" title="返回练习房间">
            <ArrowLeft aria-hidden="true" />
          </button>
          <div className="report-hero-copy">
            <span>{reportMeta?.district ?? "Practice Zone"} · Battle Report</span>
            <h1>{activeScenario.title} 战绩报告</h1>
            <p>{practiceReport.summary}</p>
          </div>
          <div className={`report-level-badge ${practiceReport.metrics.report_level}`}>
            <Sparkles aria-hidden="true" />
            <span>{practiceReport.metrics.report_level === "advanced" ? "进阶报告" : "标准报告"}</span>
          </div>
        </header>

        <section className="report-layout" aria-label="practice report">
          <section className="score-command">
            <div className="score-orbit" aria-label={`综合得分 ${practiceReport.scores.overall}`}>
              <span>{practiceReport.scores.overall}</span>
              <small>Overall</small>
            </div>
            <div className="score-copy">
              <span>Rank Signal</span>
              <h2>{practiceReport.scores.overall >= 85 ? "High Clear" : practiceReport.scores.overall >= 70 ? "Solid Clear" : "First Clear"}</h2>
              <p>{generatedBy}</p>
            </div>
          </section>

          <section className="score-grid" aria-label="score breakdown">
            {scoreItems.map((score) => (
              <article className="score-tile" key={score.key}>
                <div>
                  <span>{score.label}</span>
                  <strong>{score.value}</strong>
                </div>
                <p>{score.caption}</p>
                <meter min="0" max="100" value={score.value}>
                  {score.value}
                </meter>
              </article>
            ))}
          </section>

          <section className="report-panel badge-panel" aria-label="badges">
            <div className="report-panel-title">
              <Trophy aria-hidden="true" />
              <span>解锁徽章</span>
            </div>
            <div className="badge-row">
              {practiceReport.badges.map((badge) => (
                <span key={badge}>{badge}</span>
              ))}
            </div>
          </section>

          <section className="report-panel metrics-panel" aria-label="learning metrics">
            <div className="report-panel-title">
              <Target aria-hidden="true" />
              <span>量化反馈</span>
            </div>
            <div className="metric-grid">
              <div>
                <span>用户轮次</span>
                <strong>{practiceReport.metrics.user_turns}</strong>
              </div>
              <div>
                <span>英文词数</span>
                <strong>{practiceReport.metrics.word_count}</strong>
              </div>
              <div>
                <span>平均长度</span>
                <strong>{practiceReport.metrics.average_words_per_user_turn}</strong>
              </div>
              <div>
                <span>目标命中</span>
                <strong>{practiceReport.metrics.target_expression_hits.length}</strong>
              </div>
            </div>
            {practiceReport.metrics.llm_error ? (
              <div className="message-bar error">
                <AlertCircle aria-hidden="true" />
                <span>LLM 兜底：{practiceReport.metrics.llm_error}</span>
              </div>
            ) : null}
          </section>

          <section className="report-panel strengths-panel" aria-label="strengths">
            <div className="report-panel-title">
              <CheckCircle2 aria-hidden="true" />
              <span>本局优势</span>
            </div>
            <div className="insight-list">
              {practiceReport.strengths.map((strength) => (
                <p key={strength}>{strength}</p>
              ))}
            </div>
          </section>

          <section className="report-panel corrections-panel" aria-label="corrections">
            <div className="report-panel-title">
              <ShieldCheck aria-hidden="true" />
              <span>表达纠错</span>
            </div>
            <div className="correction-list">
              {practiceReport.corrections.map((correction) => (
                <article className={`correction-card ${correction.severity}`} key={`${correction.original}-${correction.suggestion}`}>
                  <span>{correction.severity.toUpperCase()}</span>
                  <strong>{correction.original}</strong>
                  <p>{correction.suggestion}</p>
                  <small>{correction.reason}</small>
                </article>
              ))}
            </div>
          </section>

          <section className="report-panel drills-panel" aria-label="review drills">
            <div className="report-panel-title">
              <Star aria-hidden="true" />
              <span>复练任务</span>
            </div>
            <div className="drill-list">
              {practiceReport.drills.map((drill, index) => (
                <article className="drill-card" key={`${drill.title}-${drill.target_expression}`}>
                  <span>Quest {index + 1}</span>
                  <strong>{drill.title}</strong>
                  <p>{drill.prompt}</p>
                  <small>{drill.target_expression}</small>
                </article>
              ))}
            </div>
          </section>
        </section>
      </main>
    );
  }

  if (view === "room" && createdSession && activeScenario) {
    const ActiveIcon = scenarioIcons[activeScenario.id] ?? Sparkles;

    return (
      <main className="practice-shell">
        <audio autoPlay ref={remoteAudioRef}>
          <track kind="captions" />
        </audio>

        <header className="room-brief">
          <button className="icon-button" onClick={returnToMap} type="button" title="返回地图">
            <ArrowLeft aria-hidden="true" />
          </button>
          <div className="room-title">
            <span>{activeMeta?.district ?? "Practice Zone"}</span>
            <h1>{activeScenario.title}</h1>
          </div>
          <div className={`voice-pill ${realtimeStatus}`}>
            <Radio aria-hidden="true" />
            <span>{statusMeta.label}</span>
          </div>
        </header>

        <section className="practice-layout" aria-label="practice room">
          <section className={`coach-stage scenario-${activeScenario.id}`} aria-label="voice stage">
            <ScenarioBackdrop scenarioId={activeScenario.id} />
            <div className="stage-grid" aria-hidden="true" />
            <div className={`voice-core ${realtimeStatus}`}>
              <span className="voice-ring" />
              <span className="voice-avatar">
                <ActiveIcon />
              </span>
              <span className="wave-bar one" />
              <span className="wave-bar two" />
              <span className="wave-bar three" />
            </div>

            <div className="stage-copy">
              <span>{statusMeta.hint}</span>
              <h2>{activeScenario.role}</h2>
              <p>{roomNotice}</p>
            </div>

            <div className="stage-actions">
              <button
                className="primary-voice-button"
                disabled={isConnectingRealtime || realtimeStatus === "listening" || realtimeStatus === "speaking"}
                onClick={startSelectedVoiceProvider}
                type="button"
              >
                {isConnectingRealtime ? <Loader2 className="spin" aria-hidden="true" /> : <Mic aria-hidden="true" />}
                <span>{isConnectingRealtime ? "连接中" : voiceProvider === "gemini" ? "开始 Gemini" : "开始语音"}</span>
              </button>
              <button
                className="ghost-voice-button"
                disabled={realtimeStatus === "idle" || realtimeStatus === "ended"}
                onClick={() => closeRealtimeConnection("ended")}
                type="button"
              >
                <CircleStop aria-hidden="true" />
                <span>结束</span>
              </button>
            </div>
          </section>

          <aside className="mission-console" aria-label="mission console">
            <div className="console-header">
              <span>Mission Console</span>
              <strong>{createdSession.difficulty.toUpperCase()}</strong>
            </div>
            <div className="provider-switch" aria-label="voice provider">
              {voiceProviderOptions.map((provider) => (
                <button
                  className={provider.id === voiceProvider ? "is-active" : ""}
                  key={provider.id}
                  onClick={() => {
                    closeRealtimeConnection("idle");
                    setVoiceProvider(provider.id);
                    setRoomError("");
                    setRoomNotice(
                      provider.id === "gemini"
                        ? "Gemini Live 将使用 WebSocket 音频流"
                        : "OpenAI Realtime 将使用 WebRTC 语音链路",
                    );
                  }}
                  type="button"
                >
                  <span>{provider.label}</span>
                  <small>{provider.caption}</small>
                </button>
              ))}
            </div>
            <div className="console-metric">
              <Trophy aria-hidden="true" />
              <div>
                <span>奖励</span>
                <strong>{activeMeta?.reward ?? "练习徽章"}</strong>
              </div>
            </div>
            <div className="console-metric">
              <Target aria-hidden="true" />
              <div>
                <span>目标</span>
                <strong>{activeMeta?.checkpoint ?? "完成一次自然对话"}</strong>
              </div>
            </div>
            <div className="room-skill-deck">
              {activeScenario.target_expressions.map((expression) => (
                <span key={expression}>{expression}</span>
              ))}
            </div>
          </aside>

          <section className="transcript-panel" aria-label="conversation transcript">
            <div className="transcript-header">
              <div>
                <span>Live Transcript</span>
                <strong>{turns.length} turns saved</strong>
              </div>
              <div className="turn-counter">
                <Headphones aria-hidden="true" />
                <span>{userTurnCount}/5</span>
              </div>
            </div>

            {roomError ? (
              <div className="message-bar error">
                <AlertCircle aria-hidden="true" />
                <span>{roomError}</span>
              </div>
            ) : null}

            <div className="transcript-feed">
              {turns.length === 0 ? (
                <div className="empty-transcript">
                  <Waves aria-hidden="true" />
                  <span>等待第一轮英文对话</span>
                </div>
              ) : (
                turns.map((turn) => (
                  <article className={`turn-card ${turn.role}`} key={turn.turn_id}>
                    <span>{turn.role === "user" ? "You" : "AI Coach"}</span>
                    <p>{turn.text}</p>
                  </article>
                ))
              )}
            </div>

            {reportError ? (
              <div className="message-bar error">
                <AlertCircle aria-hidden="true" />
                <span>{reportError}</span>
              </div>
            ) : null}

            <div className="report-action-row">
              <button
                className="report-action standard"
                disabled={isGeneratingReport}
                onClick={() => void generateReport("standard")}
                type="button"
              >
                {isGeneratingReport ? <Loader2 className="spin" aria-hidden="true" /> : <Trophy aria-hidden="true" />}
                <span>生成标准报告</span>
              </button>
              <button
                className="report-action advanced"
                disabled={isGeneratingReport}
                onClick={() => void generateReport("advanced")}
                type="button"
              >
                {isGeneratingReport ? <Loader2 className="spin" aria-hidden="true" /> : <Sparkles aria-hidden="true" />}
                <span>生成进阶报告</span>
              </button>
            </div>

            <div className="room-footer-strip">
              <Volume2 aria-hidden="true" />
              <span>Session {createdSession.session_id.slice(0, 8)}</span>
            </div>
          </section>
        </section>
      </main>
    );
  }

  return (
    <main className="quest-shell">
      <header className="hero-brief">
        <div className="hero-copy">
          <div className="brand-lockup">
            <span className="brand-mark">
              <Sparkles aria-hidden="true" />
            </span>
            <span>SpeakQuest</span>
          </div>
          <h1>选择今天的口语冒险路线</h1>
          <p>每条路线都是一段真实对话，完成后解锁反馈、徽章和关键句复练。</p>
        </div>

        <div className="status-rail" aria-label="practice progress">
          <div className="status-chip">
            <Flame aria-hidden="true" />
            <span>Day 1</span>
          </div>
          <div className="status-chip">
            <Zap aria-hidden="true" />
            <span>0 / 120 XP</span>
          </div>
          <div className="status-chip">
            <Radio aria-hidden="true" />
            <span>Coach Link</span>
          </div>
        </div>
      </header>

      <section className="quest-layout" aria-label="scenario workspace">
        <section className="map-panel" aria-label="adventure map">
          <div className="panel-title">
            <div>
              <span>Adventure Map</span>
              <strong>{scenarios.length || 3} 条路线</strong>
            </div>
            <Route aria-hidden="true" />
          </div>

          {isLoading ? (
            <div className="state-panel">
              <Loader2 className="spin" aria-hidden="true" />
              <span>加载场景中</span>
            </div>
          ) : (
            <div className="route-board">
              <span className="route-line" aria-hidden="true" />
              {scenarios.map((scenario) => {
                const Icon = scenarioIcons[scenario.id] ?? Sparkles;
                const isSelected = scenario.id === selectedScenarioId;
                const meta = scenarioMeta[scenario.id];

                return (
                  <button
                    className={`map-node ${isSelected ? "is-selected" : ""}`}
                    key={scenario.id}
                    onClick={() => selectScenario(scenario)}
                    style={{ "--accent": scenario.accent_color } as AccentStyle}
                    type="button"
                  >
                    <span className="node-pin">
                      <Icon aria-hidden="true" />
                    </span>
                    <span className="node-body">
                      <span className="node-kicker">
                        <span>{meta?.chapter ?? "Level"}</span>
                        <span>{meta?.district ?? "Practice Zone"}</span>
                      </span>
                      <strong>{scenario.title}</strong>
                      <small>{scenario.subtitle}</small>
                      <span className="node-stats">
                        <span>{scenario.default_difficulty.toUpperCase()}</span>
                        <span>{meta?.time ?? "5 min"}</span>
                        <span>{meta?.xp ?? 100} XP</span>
                      </span>
                    </span>
                    <span className="node-signal">{meta?.signal ?? "Dialogue"}</span>
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <aside className="coach-link" aria-label="selected scenario">
          {selectedScenario ? (
            <>
              <div className="link-header">
                <div className="signal-avatar" aria-hidden="true">
                  <span />
                  <Mic2 />
                </div>
                <div>
                  <span>AI COACH LINK</span>
                  <strong>{selectedScenario.role}</strong>
                </div>
              </div>

              <div className="brief-strip">
                <div>
                  <span>通关奖励</span>
                  <strong>{selectedMeta?.reward ?? "练习徽章"}</strong>
                </div>
                <Trophy aria-hidden="true" />
              </div>

              <div className="mission-brief">
                <span>Mission Brief</span>
                <p>{selectedScenario.user_goal}</p>
              </div>

              <div className="objective-list" aria-label="quest checklist">
                <span>
                  <Check aria-hidden="true" />
                  {selectedMeta?.checkpoint ?? "完成一次自然对话"}
                </span>
                <span>
                  <ShieldCheck aria-hidden="true" />
                  结束后获得量化报告
                </span>
              </div>

              <div className="loadout-grid" aria-label="difficulty">
                {difficultyOptions.map((option) => (
                  <button
                    className={option.id === difficulty ? "is-active" : ""}
                    key={option.id}
                    onClick={() => {
                      setDifficulty(option.id);
                      setCreatedSession(null);
                    }}
                    type="button"
                  >
                    <Target aria-hidden="true" />
                    <strong>{option.label}</strong>
                    <span>{option.description}</span>
                  </button>
                ))}
              </div>

              <div className="skill-deck">
                <strong>
                  <Star aria-hidden="true" />
                  技能卡
                </strong>
                <div>
                  {selectedScenario.target_expressions.map((expression) => (
                    <span key={expression}>{expression}</span>
                  ))}
                </div>
              </div>

              {error ? (
                <div className="message-bar error">
                  <AlertCircle aria-hidden="true" />
                  <span>{error}</span>
                </div>
              ) : null}

              {createdSession ? (
                <div className="message-bar success">
                  <CheckCircle2 aria-hidden="true" />
                  <span>Session 已创建：{createdSession.session_id.slice(0, 8)}</span>
                </div>
              ) : null}

              <button className="start-button" disabled={isCreating || isLoading} onClick={createSession} type="button">
                {isCreating ? <Loader2 className="spin" aria-hidden="true" /> : <Play aria-hidden="true" />}
                <span>{isCreating ? "锁定中" : "锁定副本"}</span>
              </button>
            </>
          ) : (
            <div className="state-panel">
              <AlertCircle aria-hidden="true" />
              <span>{error || "请选择一个场景"}</span>
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}

export default App;
