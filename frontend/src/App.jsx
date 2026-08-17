import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000/api";
const AI_CHAT_ENDPOINT = import.meta.env.VITE_AI_CHAT_ENDPOINT ?? `${API_BASE}/assistant/chat`;

const initialInputData = {
  object_name: "",
  customer_name: "Блок геологии и разработки",
  goal: "",
  deadline: "2026-09-30",
  source_data_ready: false,
  needs_3d_model: false,
  requires_subcontractor: false,
  subcontract_share_percent: "",
  separate_subcontract_estimate: false,
};

const demoQuery = "Нужно оценить запасы по объекту и подготовить проектно-технический документ";

const intentLabels = {
  service_search: "Поиск услуги",
  contractor_selection: "Выбор исполнителя",
  similar_cases: "Поиск аналогов",
  draft_generation: "Генерация ТЗ",
};

const documentLabels = {
  tz: "Техническое задание",
  calendar_plan: "Календарный план",
  cost_estimate: "Расчет стоимости",
};

function normalizeInputData(inputData) {
  return {
    ...initialInputData,
    ...inputData,
    subcontract_share_percent:
      inputData?.subcontract_share_percent === null || inputData?.subcontract_share_percent === undefined
        ? ""
        : String(inputData.subcontract_share_percent),
  };
}

function payloadInputData(inputData) {
  return {
    ...inputData,
    object_name: inputData.object_name || null,
    customer_name: inputData.customer_name || null,
    goal: inputData.goal || null,
    deadline: inputData.deadline || null,
    subcontract_share_percent:
      inputData.subcontract_share_percent === "" ? null : Number(inputData.subcontract_share_percent),
  };
}

function App() {
  const [activeTab, setActiveTab] = useState("search");
  const [query, setQuery] = useState(demoQuery);
  const [searchResponse, setSearchResponse] = useState(null);
  const [selectedResult, setSelectedResult] = useState(null);
  const [draft, setDraft] = useState(null);
  const [draftInput, setDraftInput] = useState(initialInputData);
  const [analytics, setAnalytics] = useState(null);
  const [status, setStatus] = useState("Готов к демонстрации");
  const [isLoading, setIsLoading] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([{ id: "assistant-start", role: "assistant", text: "Готов." }]);
  const [isAssistantLoading, setIsAssistantLoading] = useState(false);

  const results = searchResponse?.results?.products ?? [];
  const recommendations = searchResponse?.results?.recommendations ?? [];

  const selectedCompany = useMemo(() => {
    if (!selectedResult) return null;
    return selectedResult.recommended_companies?.[0] ?? null;
  }, [selectedResult]);

  useEffect(() => {
    runSearch(demoQuery);
    loadAnalytics();
  }, []);

  useEffect(() => {
    if (!draft) return;
    const timeout = window.setTimeout(() => {
      evaluateDraft({ ...draft, input_data: payloadInputData(draftInput) });
    }, 350);
    return () => window.clearTimeout(timeout);
  }, [draftInput]);

  async function request(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return response.json();
  }

  async function runSearch(nextQuery = query) {
    setIsLoading(true);
    setStatus("Ищу продукт, исполнителей и аналоги");
    try {
      const data = await request("/search/query", {
        method: "POST",
        body: JSON.stringify({ query: nextQuery, limit: 3 }),
      });
      setSearchResponse(data);
      setSelectedResult(data.results.products[0] ?? null);
      setStatus("Рекомендации готовы");
    } catch (error) {
      setStatus(`Ошибка поиска: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  }

  async function createDraft(result = selectedResult, company = selectedCompany) {
    if (!result) return;
    setIsLoading(true);
    setStatus("Формирую черновик ТЗ");
    try {
      const inputData = {
        ...initialInputData,
        object_name: "Северный блок",
        customer_name: "Блок геологии и разработки",
        goal: result.product.summary,
        deadline: "2026-09-30",
      };
      const data = await request("/drafts/from-search", {
        method: "POST",
        body: JSON.stringify({
          product_id: result.product.id,
          company_id: company?.id ?? null,
          query,
          input_data: payloadInputData(inputData),
        }),
      });
      setDraft(data.draft);
      setDraftInput(normalizeInputData(data.draft.input_data));
      setActiveTab("draft");
      setStatus("Черновик создан");
    } catch (error) {
      setStatus(`Ошибка генерации: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  }

  async function evaluateDraft(nextDraft) {
    try {
      const data = await request("/drafts/evaluate", {
        method: "POST",
        body: JSON.stringify({ draft: nextDraft }),
      });
      setDraft(data.draft);
      setStatus("Оценка готовности обновлена");
    } catch (error) {
      setStatus(`Ошибка проверки: ${error.message}`);
    }
  }

  async function loadAnalytics() {
    try {
      const data = await request("/analytics/overview");
      setAnalytics(data);
    } catch {
      setAnalytics(null);
    }
  }

  function updateDraftInput(key, value) {
    setDraftInput((current) => ({ ...current, [key]: value }));
  }

  function buildAssistantContext() {
    return {
      active_tab: activeTab,
      query,
      selected_product: selectedResult
        ? {
            id: selectedResult.product.id,
            name: selectedResult.product.name,
            summary: selectedResult.product.summary,
            reasons: selectedResult.reasons,
            companies: selectedResult.recommended_companies?.map((company) => company.name) ?? [],
          }
        : null,
      draft: draft
        ? {
            id: draft.id,
            product_name: draft.product_name,
            ready_score: draft.ready_score,
            company_name: draft.company_name,
            contract_name: draft.contract_name,
            stages: draft.stages,
            input_data: draftInput,
            risks: draft.risks,
          }
        : null,
    };
  }

  function localAssistantReply(message) {
    const value = message.toLowerCase();
    if (value.includes("сформ")) {
      return selectedResult ? "Нажмите «Сформировать ТЗ»." : "Сначала выберите продукт.";
    }
    if (value.includes("уточ") || value.includes("вопрос")) {
      return "Уточните объект, цель, срок, исходные данные и субподряд.";
    }
    if (value.includes("провер") || value.includes("риск") || value.includes("готов")) {
      if (!draft) return "Черновик ещё не создан.";
      if (!draft.risks.length) return `Готовность ${draft.ready_score}%. Критичных рисков нет.`;
      return `Готовность ${draft.ready_score}%. Риски: ${draft.risks.map((risk) => risk.message).slice(0, 3).join("; ")}.`;
    }
    if (value.includes("крат") || value.includes("резюме")) {
      if (draft) return `${draft.product_name}. Исполнитель: ${draft.company_name ?? "не выбран"}. Готовность: ${draft.ready_score}%.`;
      if (selectedResult) return `${selectedResult.product.name}. ${selectedResult.product.summary}`;
      return "Сначала выберите продукт.";
    }
    return "Могу найти услугу, проверить риски или кратко собрать ТЗ.";
  }

  async function sendAssistantMessage(text = chatInput) {
    const message = text.trim();
    if (!message || isAssistantLoading) return;
    const userMessage = { id: `user-${Date.now()}`, role: "user", text: message };
    setChatMessages((current) => [...current, userMessage]);
    setChatInput("");
    setIsAssistantLoading(true);
    try {
      const response = await fetch(AI_CHAT_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, context: buildAssistantContext(), history: chatMessages.slice(-8) }),
      });
      if (!response.ok) throw new Error("assistant_unavailable");
      const data = await response.json();
      setChatMessages((current) => [
        ...current,
        { id: `assistant-${Date.now()}`, role: "assistant", text: data.reply || localAssistantReply(message) },
      ]);
    } catch {
      setChatMessages((current) => [
        ...current,
        { id: `assistant-${Date.now()}`, role: "assistant", text: localAssistantReply(message) },
      ]);
    } finally {
      setIsAssistantLoading(false);
    }
  }

  async function createDraftFromChat() {
    if (!selectedResult) {
      await sendAssistantMessage("Сформировать ТЗ");
      return;
    }
    setChatMessages((current) => [...current, { id: `user-${Date.now()}`, role: "user", text: "Сформировать ТЗ" }]);
    await createDraft(selectedResult);
    setChatMessages((current) => [...current, { id: `assistant-${Date.now()}`, role: "assistant", text: "Черновик создан." }]);
  }

  async function exportPackage() {
    if (!draft) return;
    setStatus("Готовлю пакет DOCX/XLSX");
    try {
      const response = await fetch(`${API_BASE}/drafts/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draft: { ...draft, input_data: payloadInputData(draftInput) } }),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `prostor-${draft.id}-package.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setStatus("Пакет DOCX/XLSX выгружен");
    } catch (error) {
      setStatus(`Ошибка экспорта: ${error.message}`);
    }
  }

  return (
    <main className={`app-shell ${isChatOpen ? "chat-open" : "chat-closed"}`}>
      <aside className="sidebar">
        <section className="brand">
          <span className="eyebrow">PROSTOR MVP</span>
          <h1>Умный конструктор ТЗ</h1>
          <p>Поиск продукта, подбор исполнителя, RequestDraft и проверка рисков в одном рабочем сценарии.</p>
        </section>

        <nav className="tabs" aria-label="Разделы MVP">
          <button className={activeTab === "search" ? "active" : ""} onClick={() => setActiveTab("search")}>
            Поиск
          </button>
          <button className={activeTab === "draft" ? "active" : ""} onClick={() => setActiveTab("draft")}>
            Конструктор
          </button>
          <button className={activeTab === "analytics" ? "active" : ""} onClick={() => setActiveTab("analytics")}>
            Аналитика
          </button>
        </nav>

        <section className="source-card">
          <span className="eyebrow">Данные задания</span>
          <dl>
            <div><dt>Компании</dt><dd>13</dd></div>
            <div><dt>Договоры</dt><dd>20</dd></div>
            <div><dt>Продукты</dt><dd>31-48</dd></div>
            <div><dt>Операции</dt><dd>318</dd></div>
            <div><dt>Расценки</dt><dd>2780</dd></div>
          </dl>
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Единый демо-поток</span>
            <h2>{activeTab === "search" ? "AI-агент поиска" : activeTab === "draft" ? "RequestDraft" : "Контур управления"}</h2>
          </div>
          <span className={`status ${isLoading ? "loading" : ""}`}>{status}</span>
        </header>

        {activeTab === "search" && (
          <SearchView
            query={query}
            setQuery={setQuery}
            runSearch={runSearch}
            response={searchResponse}
            results={results}
            selectedResult={selectedResult}
            setSelectedResult={setSelectedResult}
            recommendations={recommendations}
            createDraft={createDraft}
          />
        )}

        {activeTab === "draft" && (
          <DraftView
            draft={draft}
            draftInput={draftInput}
            updateDraftInput={updateDraftInput}
            exportPackage={exportPackage}
            goSearch={() => setActiveTab("search")}
          />
        )}

        {activeTab === "analytics" && <AnalyticsView analytics={analytics} />}
      </section>

      <AssistantSidebar
        isOpen={isChatOpen}
        onToggle={() => setIsChatOpen((current) => !current)}
        messages={chatMessages}
        input={chatInput}
        setInput={setChatInput}
        onSend={sendAssistantMessage}
        onCreateDraft={createDraftFromChat}
        isLoading={isAssistantLoading}
        hasDraft={Boolean(draft)}
        hasSelectedResult={Boolean(selectedResult)}
      />
    </main>
  );
}

function SearchView({
  query,
  setQuery,
  runSearch,
  response,
  results,
  selectedResult,
  setSelectedResult,
  recommendations,
  createDraft,
}) {
  return (
    <div className="grid two-columns">
      <section className="panel search-panel">
        <form
          className="search-box"
          onSubmit={(event) => {
            event.preventDefault();
            runSearch();
          }}
        >
          <label>
            <span>Запрос пользователя</span>
            <textarea value={query} onChange={(event) => setQuery(event.target.value)} rows={4} />
          </label>
          <div className="actions">
            <button type="submit">Найти решение</button>
            <button type="button" className="secondary" onClick={() => runSearch(demoQuery)}>
              Демо-запрос
            </button>
          </div>
        </form>

        {response && (
          <div className="intent-line">
            <span>Интент</span>
            <strong>{intentLabels[response.detected_intent]}</strong>
          </div>
        )}

        <div className="result-list">
          {results.map((result) => (
            <button
              key={result.product.id}
              className={`result-card ${selectedResult?.product.id === result.product.id ? "selected" : ""}`}
              onClick={() => setSelectedResult(result)}
            >
              <span className="score">{result.score}</span>
              <strong>{result.product.name}</strong>
              <small>{result.product.summary}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="panel details-panel">
        {selectedResult ? (
          <>
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Рекомендация</span>
                <h3>{selectedResult.product.name}</h3>
              </div>
              <button onClick={() => createDraft(selectedResult)}>Сформировать ТЗ</button>
            </div>

            <ReasonList title="Почему подходит" items={selectedResult.reasons} />

            <div className="split">
              <InfoGroup title="Исполнители">
                {selectedResult.recommended_companies.map((company) => (
                  <article className="compact-card" key={company.id}>
                    <strong>{company.name}</strong>
                    <span>Рейтинг {company.rating.toFixed(1)}</span>
                    <p>{company.description}</p>
                  </article>
                ))}
              </InfoGroup>

              <InfoGroup title="Похожие работы">
                {selectedResult.similar_cases.map((item) => (
                  <article className="compact-card" key={item.id}>
                    <strong>{item.title}</strong>
                    <p>{item.summary}</p>
                  </article>
                ))}
              </InfoGroup>
            </div>

            <ReasonList title="Что уточнить перед ТЗ" items={recommendations} />
          </>
        ) : (
          <EmptyState text="Введите запрос, чтобы получить продукты и исполнителей." />
        )}
      </section>
    </div>
  );
}

function DraftView({ draft, draftInput, updateDraftInput, exportPackage, goSearch }) {
  if (!draft) {
    return (
      <section className="panel">
        <EmptyState text="Черновик еще не создан. Перейдите в поиск и нажмите «Сформировать ТЗ»." />
        <button onClick={goSearch}>К поиску</button>
      </section>
    );
  }

  const readyClass = draft.ready_score >= 70 ? "good" : draft.ready_score >= 40 ? "warn" : "bad";

  return (
    <div className="grid draft-grid">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Черновик {draft.id}</span>
            <h3>{draft.product_name}</h3>
          </div>
          <button onClick={exportPackage}>Экспорт пакета</button>
        </div>

        <div className="form-grid">
          <TextInput label="Объект" value={draftInput.object_name} onChange={(value) => updateDraftInput("object_name", value)} />
          <TextInput label="Заказчик" value={draftInput.customer_name} onChange={(value) => updateDraftInput("customer_name", value)} />
          <label className="span-2">
            <span>Цель работ</span>
            <textarea value={draftInput.goal} onChange={(event) => updateDraftInput("goal", event.target.value)} rows={4} />
          </label>
          <TextInput label="Плановый срок" type="date" value={draftInput.deadline} onChange={(value) => updateDraftInput("deadline", value)} />
          <TextInput
            label="Доля субподряда, %"
            type="number"
            value={draftInput.subcontract_share_percent}
            onChange={(value) => updateDraftInput("subcontract_share_percent", value)}
          />
        </div>

        <div className="toggle-grid">
          <Toggle label="Исходные данные готовы" checked={draftInput.source_data_ready} onChange={(value) => updateDraftInput("source_data_ready", value)} />
          <Toggle label="Нужна 3D-модель" checked={draftInput.needs_3d_model} onChange={(value) => updateDraftInput("needs_3d_model", value)} />
          <Toggle label="Нужен субподряд" checked={draftInput.requires_subcontractor} onChange={(value) => updateDraftInput("requires_subcontractor", value)} />
          <Toggle
            label="Отдельный РС по субподряду"
            checked={draftInput.separate_subcontract_estimate}
            onChange={(value) => updateDraftInput("separate_subcontract_estimate", value)}
          />
        </div>

        <TemplateStructure draft={draft} draftInput={draftInput} />
      </section>

      <aside className="panel inspector">
        <div className={`ready-meter ${readyClass}`}>
          <span>Готовность</span>
          <strong>{draft.ready_score}%</strong>
        </div>

        <InfoGroup title="Исполнитель и договор">
          <article className="compact-card">
            <strong>{draft.company_name ?? "Не выбран"}</strong>
            <p>{draft.contract_name ?? "Договор будет выбран после уточнения продукта."}</p>
          </article>
        </InfoGroup>

        <InfoGroup title="Этапы">
          <div className="chips">
            {draft.stages.map((stage) => <span key={stage}>{stage}</span>)}
          </div>
        </InfoGroup>

        <InfoGroup title="Риски и рекомендации">
          {draft.risks.length ? (
            draft.risks.map((risk) => (
              <article className={`risk ${risk.severity}`} key={risk.code}>
                <strong>{risk.message}</strong>
                <p>{risk.recommendation}</p>
              </article>
            ))
          ) : (
            <p className="muted">Критичных рисков не найдено.</p>
          )}
        </InfoGroup>

        <InfoGroup title="Пакет документов">
          <div className="doc-list">
            {draft.documents.map((document) => (
              <span key={document.kind} className={document.status}>
                {documentLabels[document.kind]} · {document.status === "ready" ? "готов" : "план"}
              </span>
            ))}
          </div>
        </InfoGroup>
      </aside>
    </div>
  );
}

function AssistantSidebar({
  isOpen,
  onToggle,
  messages,
  input,
  setInput,
  onSend,
  onCreateDraft,
  isLoading,
  hasDraft,
  hasSelectedResult,
}) {
  if (!isOpen) {
    return <button className="chat-fab" onClick={onToggle}>AI-чат</button>;
  }

  const quickActions = [
    { label: "Что уточнить", action: () => onSend("Что уточнить для ТЗ?") },
    { label: "Проверить", action: () => onSend("Проверить готовность и риски") },
    { label: "Краткое ТЗ", action: () => onSend("Краткое резюме ТЗ") },
    { label: "Сформировать", action: onCreateDraft, disabled: !hasSelectedResult },
  ];

  return (
    <aside className="assistant-sidebar" aria-label="AI-помощник по ТЗ">
      <header className="assistant-header">
        <div>
          <span className="eyebrow">AI-помощник</span>
          <h3>Чат по ТЗ</h3>
        </div>
        <button className="icon-button" type="button" onClick={onToggle} aria-label="Скрыть чат">×</button>
      </header>

      <div className="assistant-context">
        {hasDraft ? "Черновик подключён" : hasSelectedResult ? "Продукт выбран" : "Ожидаю продукт"}
      </div>

      <div className="quick-actions">
        {quickActions.map((item) => (
          <button key={item.label} type="button" className="secondary" onClick={item.action} disabled={item.disabled || isLoading}>
            {item.label}
          </button>
        ))}
      </div>

      <div className="message-list">
        {messages.map((message) => (
          <div className={`message ${message.role}`} key={message.id}>{message.text}</div>
        ))}
        {isLoading && <div className="message assistant">...</div>}
      </div>

      <form
        className="assistant-input"
        onSubmit={(event) => {
          event.preventDefault();
          onSend();
        }}
      >
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSend();
            }
          }}
          placeholder="Короткий запрос по ТЗ"
          rows={3}
        />
        <button type="submit" disabled={!input.trim() || isLoading}>Отправить</button>
      </form>
    </aside>
  );
}

function TemplateStructure({ draft, draftInput }) {
  const sections = [
    {
      title: "1. Реквизиты",
      rows: [
        ["Продукт", draft.product_name],
        ["Заказчик", draftInput.customer_name || "не заполнен"],
        ["Исполнитель", draft.company_name ?? "не выбран"],
        ["Договор", draft.contract_name ?? "не выбран"],
      ],
    },
    {
      title: "2. Цели и периметр",
      rows: [
        ["Объект", draftInput.object_name || "не заполнен"],
        ["Цель", draftInput.goal || "не заполнена"],
      ],
    },
    {
      title: "3. Сроки и этапы",
      rows: [
        ["Срок", draftInput.deadline || "не заполнен"],
        ["Этапы", draft.stages.join(" → ")],
      ],
    },
    {
      title: "4. Условия выполнения",
      rows: [
        ["Исходные данные", draftInput.source_data_ready ? "готовы" : "уточнить"],
        ["3D-модель", draftInput.needs_3d_model ? "нужна" : "не нужна"],
        ["Субподряд", draftInput.requires_subcontractor ? `${draftInput.subcontract_share_percent || 0}%` : "не требуется"],
      ],
    },
    {
      title: "5. Документы и качество",
      rows: [
        ["Приложение 1", "Техническое задание"],
        ["Приложение 2", "Коммерческое предложение"],
        ["Приложение 3", "Расчёт стоимости"],
        ["Контроль", "приёмка по этапам"],
      ],
    },
  ];

  return (
    <section className="template-structure">
      <div className="section-title">
        <span className="eyebrow">По примеру ТЗ</span>
        <h4>Структура документа</h4>
      </div>
      <div className="template-grid">
        {sections.map((section) => (
          <article className="template-section" key={section.title}>
            <h5>{section.title}</h5>
            <dl>
              {section.rows.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}

function AnalyticsView({ analytics }) {
  if (!analytics) {
    return (
      <section className="panel">
        <EmptyState text="Аналитика будет доступна после запуска backend." />
      </section>
    );
  }

  return (
    <div className="grid analytics-grid">
      <Metric label="Продукты" value={analytics.total_products} />
      <Metric label="Компании" value={analytics.total_companies} />
      <Metric label="Активные договоры" value={analytics.total_active_contracts} />
      <Metric label="Исторические кейсы" value={analytics.total_historical_cases} />

      <section className="panel span-2">
        <InfoGroup title="Популярные продукты">
          <div className="chips">
            {analytics.most_requested_products.map((product) => <span key={product}>{product}</span>)}
          </div>
        </InfoGroup>
      </section>

      <section className="panel span-2">
        <ReasonList title="Частые ошибки в заявках" items={analytics.common_risk_patterns} />
      </section>

      <section className="panel span-2">
        <ReasonList title="Типовые этапы работ" items={analytics.common_stages ?? []} />
      </section>

      <section className="panel span-2">
        <ReasonList title="Кандидаты на продуктовую упаковку" items={analytics.product_packaging_candidates ?? []} />
      </section>

      <section className="panel span-2">
        <ReasonList title="Популярные связки услуг" items={analytics.popular_service_combinations ?? []} />
      </section>

      <section className="panel span-2">
        <ReasonList title="Часто пустые поля" items={analytics.empty_field_patterns ?? []} />
      </section>
    </div>
  );
}

function TextInput({ label, value, onChange, type = "text" }) {
  return (
    <label>
      <span>{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function Metric({ label, value }) {
  return (
    <section className="panel metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </section>
  );
}

function InfoGroup({ title, children }) {
  return (
    <div className="info-group">
      <h4>{title}</h4>
      {children}
    </div>
  );
}

function ReasonList({ title, items }) {
  return (
    <InfoGroup title={title}>
      <ul className="reason-list">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </InfoGroup>
  );
}

function EmptyState({ text }) {
  return <p className="empty">{text}</p>;
}

export default App;
