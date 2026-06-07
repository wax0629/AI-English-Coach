# AI English Coach
demo演示视频链接：https://www.bilibili.com/video/BV1ZJEb6oEGk?vd_source=6f06d2bd1b7429af5b3816b9496a2749

AI English Coach 是一款面向指定场景的 AI 英语口语陪练 MVP。它以“真实对话训练”为核心，让用户在求职面试、餐厅点餐、商务会议等场景中完成语音对话，并在课后获得量化报告、表达纠错、关键句复练和弱点记忆。

项目目标不是做一个普通聊天机器人，而是形成一条可演示、可量化、可持续改进的口语训练闭环：

```text
场景选择 -> 实时语音对话 -> 对话转写 -> 课后报告 -> 关键句复练 -> 弱点记忆 -> 下一轮定制训练
```

## 核心功能

- 场景选择：支持求职面试、餐厅点餐、商务会议三条练习路线。
- 实时语音对话：支持 OpenAI Realtime 与 Gemini Live 两条语音链路。
- 对话转写保存：保存用户和 AI 的对话 turn，用于生成报告与后续复盘。
- 课后报告：输出总分、流利度、语法、词汇、目标完成度、量化指标、优势、纠错和复练任务。
- LLM 报告增强：默认使用 DeepSeek 生成报告增强内容，也支持 Gemini；模型异常时自动回退到规则报告。
- Azure 发音评测：对关键句复练进行准确度、流利度、完整度、韵律和单词级反馈。
- 关键句复练：将报告中的建议转成可录音复练的任务，达标后推进进度。
- Learner Profile 弱点记忆：记录高频表达问题和未命中目标表达，并按当前场景优先注入到下一轮 AI 教练提示中。
- 演示兜底：提供 Demo Control 和演示对话载入入口，即使语音 API 波动，也能完整展示“对话 -> 报告 -> 复练 -> 记忆”闭环。

## 项目亮点

- 学习闭环完整：不是只聊天，而是把练习结果转化为可复练的任务。
- 纠错时机克制：对话中尽量保持自然交流，课后集中纠错，减少打断感。
- 可量化反馈：用分数、轮次、词数、目标表达命中等指标衡量进步。
- 场景化记忆：面试、点餐、会议优先使用各自场景的弱点记忆，通用弱点作为兜底。
- 多模型兼容：语音链路和报告生成链路都有可替换方案，降低单一服务不可用的风险。
- 演示稳定性：无 API 或 API 波动时，可以使用演示对话和规则兜底跑完整流程。
- 游戏化 UI：以路线、徽章、进度、复练任务组织学习体验，适合三天 MVP 演示。

## 技术架构

```text
frontend/
  React + Vite + TypeScript
  负责场景工作台、练习房间、报告页、复练 UI、语音录制与音频格式转换

backend/
  FastAPI + SQLAlchemy + SQLite
  负责场景/session/turn/report/profile/readiness API

AI / Speech Providers
  OpenAI Realtime: 实时语音对话
  Gemini Live: 备用实时语音对话
  DeepSeek / Gemini: 报告增强 LLM
  Azure Speech: 发音评测
```

## 快速启动

### 1. 克隆项目

```powershell
git clone https://github.com/wax0629/AI-English-Coach.git
cd "AI-English-Coach"
```

### 2. 配置环境变量

复制示例文件：

```powershell
Copy-Item .env.example .env
```

最小演示可以不填 API Key，系统仍可通过演示对话和规则报告跑通核心闭环。需要真实语音和发音评分时，再按需填写下面这些配置：

```env
OPENAI_API_KEY=
GEMINI_API_KEY=
DEEPSEEK_API_KEY=
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
```

常用配置说明：

- `OPENAI_API_KEY`：用于 OpenAI Realtime 语音对话。
- `GEMINI_API_KEY`：用于 Gemini Live 语音对话，也可作为报告增强备选。
- `REPORT_LLM_PROVIDER`：报告增强提供方，默认 `deepseek`，可改为 `gemini` 或 `rules`。
- `DEEPSEEK_API_KEY`：用于 DeepSeek 报告增强。
- `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION`：用于 Azure Pronunciation Assessment。
- `DATABASE_URL`：默认 `sqlite:///./data/coach.db`，后端启动时自动初始化 SQLite 数据库。
- `BACKEND_CORS_ORIGINS`：默认允许 Vite 的 `5173` 端口。
- `VITE_API_BASE_URL`：前端 API 地址，代码默认也是 `http://127.0.0.1:8000`。

## API Key 获取与费用说明

> 以下信息最后确认于 2026-06-07。AI 服务价格、免费额度和模型可用性变化很快，正式部署前请以对应官网为准，并给每个服务设置预算、配额或用量告警。

### OpenAI Realtime

- 用途：驱动 OpenAI Realtime 实时语音对话。
- 项目变量：`OPENAI_API_KEY`，可选调整 `OPENAI_REALTIME_MODEL`、`OPENAI_REALTIME_VOICE`、`OPENAI_REALTIME_TRANSCRIPTION_MODEL`。
- 获取方式：
  1. 打开 [OpenAI API Keys](https://platform.openai.com/api-keys)。
  2. 登录后创建新的 secret key。
  3. 创建时立即复制保存，OpenAI 只会完整展示一次。
  4. 将 key 写入根目录 `.env` 的 `OPENAI_API_KEY`。
- 是否收费：收费。OpenAI API 与 ChatGPT Plus/Business 等订阅分开计费，Playground/API 调用也按 API 价格计费。Realtime 语音模型按音频/文本 token 或分钟计费，适合真实语音演示，但要控制时长。
- 成本建议：MVP 演示时优先使用短对话；在 OpenAI Billing 中设置 monthly budget 和提醒阈值。
- 官方参考：[OpenAI API Key 帮助](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key)、[OpenAI API Pricing](https://openai.com/api/pricing/)

### Gemini Live / Gemini Report

- 用途：`Gemini Live` 作为备用实时语音链路，`Gemini Report` 可作为报告增强备选。
- 项目变量：`GEMINI_API_KEY`，可选调整 `GEMINI_LIVE_MODEL`、`GEMINI_REPORT_MODEL`。
- 获取方式：
  1. 打开 [Google AI Studio API Keys](https://aistudio.google.com/app/apikey)。
  2. 登录 Google 账号。
  3. 创建或选择一个 Google Cloud Project。
  4. 点击创建 API key，并复制到 `.env` 的 `GEMINI_API_KEY`。
- 是否收费：有免费层，也有付费层。免费层适合开发测试，但速率和模型访问受限；开启付费层后按模型、输入/输出 token、音频等维度计费。Google AI Studio 在可用地区本身免费，但 API 生产使用通常需要关注付费层、配额和账单。
- 成本建议：报告增强优先用 Flash 类模型；Live 音频只在需要真实演示时开启。开启 Google Cloud Billing 后，务必设置预算和 API 限额。
- 官方参考：[Gemini API Key 设置](https://ai.google.dev/tutorials/setup)、[Gemini Developer API Pricing](https://ai.google.dev/gemini-api/docs/pricing)

### DeepSeek Report

- 用途：默认报告增强 LLM。标准报告使用 `DEEPSEEK_REPORT_MODEL`，进阶报告使用 `DEEPSEEK_ADVANCED_REPORT_MODEL`。
- 项目变量：`DEEPSEEK_API_KEY`，可选调整 `DEEPSEEK_BASE_URL`、`DEEPSEEK_REPORT_MODEL`、`DEEPSEEK_ADVANCED_REPORT_MODEL`。
- 获取方式：
  1. 打开 [DeepSeek Platform](https://platform.deepseek.com/)。
  2. 登录后进入 API keys 页面。
  3. 创建新的 API key，复制后写入 `.env` 的 `DEEPSEEK_API_KEY`。
  4. 如接口返回余额不足，需要在平台充值或检查 billing 状态。
- 是否收费：收费，按 token 计费。DeepSeek 官方 API 当前支持 OpenAI 兼容格式，`deepseek-v4-flash` 适合默认报告，`deepseek-v4-pro` 适合进阶报告。
- 成本建议：本项目默认选择 `deepseek-v4-flash`，因为报告生成对速度和低成本更敏感；只有用户点击“生成进阶报告”时再使用 `deepseek-v4-pro`。
- 官方参考：[DeepSeek First API Call](https://api-docs.deepseek.com/)、[DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing)

### Azure Speech Pronunciation Assessment

- 用途：关键句复练时做发音评测，返回准确度、流利度、完整度、韵律和单词级诊断。
- 项目变量：`AZURE_SPEECH_KEY`、`AZURE_SPEECH_REGION`。
- 获取方式：
  1. 打开 [Azure Portal](https://portal.azure.com/)。
  2. 创建资源时搜索并选择 Microsoft 官方的 `Speech service` / `Azure AI Speech`，不要选择第三方市场 SaaS。
  3. 选择订阅、资源组、区域和定价层。建议先选支持 Pronunciation Assessment 的区域。
  4. 创建完成后进入资源页面。
  5. 在 `Keys and Endpoint` 中复制 key，并记录资源 region，例如 `eastus`、`southeastasia`。
  6. 写入 `.env` 的 `AZURE_SPEECH_KEY` 和 `AZURE_SPEECH_REGION`。
- 是否收费：有免费层和标准层。Free F0 适合小规模测试，但有配额限制；Standard S0 按量计费。Pronunciation Assessment 的基础分数通常按 Speech to Text 价格计费，Prosody、Grammar、Vocabulary、Topic 等增强分数可能有额外费用。
- 成本建议：MVP 只评测用户主动点击复练录音的短句，不做长音频批量评测；如果出现“Azure 已识别到英文，但没有返回发音评分”，优先检查资源区域是否支持发音评测。
- 官方参考：[Azure Speech 获取 key 和 region](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/get-started-text-to-speech)、[Pronunciation Assessment 说明与计费](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/pronunciation-assessment-tool)、[Azure Speech 配额与限制](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-services-quotas-and-limits)

### 安全提醒

- 不要把真实 API Key 写进 README、前端代码或提交到 GitHub。
- `.env` 应只保存在本地或部署平台的环境变量中。
- 如果 key 泄露，立即在对应平台删除或 rotate key。
- 演示前建议只给每个服务保留最低必要额度，并开启账单提醒。

### 3. 启动后端

```powershell
cd backend
pip install -e ".[dev]"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

后端健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

服务配置状态检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/readiness
```

`/api/readiness` 只返回各服务是否已配置，不会返回任何密钥。

### 4. 启动前端

另开一个终端：

```powershell
cd frontend
npm install
npm run dev -- --port 5173
```

打开：

```text
http://127.0.0.1:5173/
```

## 演示流程

推荐演示顺序：

1. 在首页选择一个场景，例如“求职面试”或“餐厅点餐”。
2. 查看左侧路线下方的 `Demo Control`，确认服务配置状态。
3. 点击“锁定副本”进入练习房间。
4. 如果已配置语音 API，可以选择 OpenAI Realtime 或 Gemini Live 开始语音练习。
5. 如果语音链路不稳定，点击“载入演示对话”。
6. 点击“生成标准报告”或“生成进阶报告”。
7. 在报告页查看分数、量化反馈、优势、纠错和复练任务。
8. 在复练任务中录音，查看 Azure 发音评分与诊断。
9. 再次回到首页或创建新 session，观察 Learner Profile 记忆如何影响下一轮练习。

## 测试与构建

后端测试：

```powershell
cd backend
python -m pytest
```

前端测试：

```powershell
cd frontend
npm test
```

前端生产构建：

```powershell
cd frontend
npm run build
```

## 主要目录

```text
backend/
  app/
    routes/             API 路由
    scenarios.py        场景配置
    reporting.py        规则报告生成
    report_llm.py       LLM 报告增强
    pronunciation.py    Azure 发音评测解析
    learner_profile.py  弱点记忆聚合
  tests/                后端测试

frontend/
  src/
    App.tsx             主要页面与交互
    gemini-live.ts      Gemini Live 音频流
    pronunciation.ts    录音转 WAV 与评分诊断
    drill-session.ts    复练状态逻辑
    drill-reference.ts  复练朗读句生成
    learner-profile.ts  前端弱点记忆展示逻辑
    readiness.ts        服务配置状态展示逻辑
```

## API 概览

- `GET /health`：后端健康检查。
- `GET /api/readiness`：检查 OpenAI、Gemini、Azure、Report LLM 配置状态。
- `GET /api/scenarios`：获取练习场景。
- `POST /api/sessions`：创建练习 session。
- `GET /api/sessions/{session_id}/turns`：获取对话转写。
- `POST /api/conversation/turns`：保存一条对话 turn。
- `POST /api/sessions/{session_id}/demo-turns`：载入演示对话。
- `POST /api/realtime/client-secret`：创建 OpenAI Realtime 临时凭证。
- `POST /api/gemini/live-token`：创建 Gemini Live 临时 token。
- `POST /api/sessions/{session_id}/report`：生成课后报告。
- `GET /api/sessions/{session_id}/report`：读取课后报告。
- `POST /api/pronunciation/assess`：提交音频并进行发音评测。
- `GET /api/learner-profiles/{user_id}`：读取用户弱点记忆。

## 注意事项

- MVP 阶段默认用户为 `demo`，暂未接入登录系统。
- SQLite 数据库默认保存在后端运行目录下的 `data/coach.db`。
- 如果改动前端端口，需要同步调整 `BACKEND_CORS_ORIGINS`。
- 如果报告模型不可用，系统会自动回退到规则报告，报告页会显示兜底信息。
- Azure 发音评测需要官方 Azure AI Speech / Speech Service 的 key 和 region。
- 演示对话不会替代真实语音能力，它只是为了保证现场演示流程稳定。

## 当前 MVP 状态

当前版本已经覆盖三天 MVP 的核心要求：

- 场景选择
- 实时语音对话
- 对话转写保存
- 课后总结
- 发音评测
- 语法/表达纠错
- 关键句复练
- 口语能力量化反馈
- Learner Profile 弱点记忆
- 演示稳定性兜底

后续可以继续扩展登录系统、长期学习档案、更多场景、班级/教师端、IELTS/TOEFL 风格评分和更细粒度的音素级训练。
