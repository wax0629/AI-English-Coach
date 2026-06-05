import { Mic, Sparkles, Trophy } from "lucide-react";
import "./styles.css";

const highlights = [
  { icon: Mic, label: "实时语音", value: "WebRTC ready" },
  { icon: Trophy, label: "量化反馈", value: "WPM / CEFR" },
  { icon: Sparkles, label: "复练闭环", value: "Drill next" },
];

function App() {
  return (
    <main className="app-shell">
      <section className="welcome-panel" aria-labelledby="page-title">
        <div className="eyebrow">AI Speaking Coach MVP</div>
        <h1 id="page-title">AI 英语口语陪练</h1>
        <p>项目骨架已就绪。下一步将进入场景工作台。</p>
        <div className="status-pill">Task 1: FastAPI + React scaffold</div>
      </section>

      <section className="signal-grid" aria-label="MVP capability preview">
        {highlights.map((item) => (
          <article className="signal-card" key={item.label}>
            <item.icon aria-hidden="true" />
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        ))}
      </section>
    </main>
  );
}

export default App;
