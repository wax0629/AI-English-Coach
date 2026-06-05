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
import "./styles.css";

type Difficulty = "a2" | "b1" | "b2";
type AppView = "map" | "room";
type RealtimeStatus = "idle" | "connecting" | "listening" | "speaking" | "ended" | "error";

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
  listening: { label: "聆听中", hint: "LISTENING" },
  speaking: { label: "AI 回复中", hint: "COACH LIVE" },
  ended: { label: "已结束", hint: "SESSION SAVED" },
  error: { label: "连接错误", hint: "CHECK LINK" },
};

function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("");
  const [difficulty, setDifficulty] = useState<Difficulty>("b1");
  const [view, setView] = useState<AppView>("map");
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isConnectingRealtime, setIsConnectingRealtime] = useState(false);
  const [error, setError] = useState<string>("");
  const [roomError, setRoomError] = useState<string>("");
  const [roomNotice, setRoomNotice] = useState<string>("副本已锁定，等待语音链路启动");
  const [createdSession, setCreatedSession] = useState<CreatedSession | null>(null);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [realtimeStatus, setRealtimeStatus] = useState<RealtimeStatus>("idle");

  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);
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
    setError("");
  }

  function closeRealtimeConnection(nextStatus: RealtimeStatus) {
    dataChannelRef.current?.close();
    dataChannelRef.current = null;
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
      setRealtimeStatus("idle");
      setRoomNotice("副本已锁定，等待语音链路启动");
      setView("room");
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

  function returnToMap() {
    closeRealtimeConnection("ended");
    setView("map");
    setRoomError("");
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
          <section className="coach-stage" aria-label="voice stage">
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
                onClick={startRealtimeConversation}
                type="button"
              >
                {isConnectingRealtime ? <Loader2 className="spin" aria-hidden="true" /> : <Mic aria-hidden="true" />}
                <span>{isConnectingRealtime ? "连接中" : "开始语音"}</span>
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
