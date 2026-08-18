import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
const AI_CHAT_ENDPOINT = import.meta.env.VITE_AI_CHAT_ENDPOINT ?? `${API_BASE}/assistant/chat`;

const demoQuery = "Нужно оценить запасы по объекту и подготовить проектно-технический документ";

const intentLabels = {
  service_search: "Поиск услуги",
  contractor_selection: "Выбор исполнителя",
  similar_cases: "Поиск аналогов",
  draft_generation: "Генерация ТЗ",
};

const sourceLabels = { template: "шаблон", manual: "вручную", ai: "ИИ" };
const statusLabels = { draft: "черновик", ready: "готово", archived: "архив" };

const emptyInput = {
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

const emptyNewTz = {
  template_key: "",
  object_name: "",
  customer_name: "Блок геологии и разработки",
  executor_name: "",
  contract_name: "",
  city: "",
  deadline: "2026-09-30",
  goal: "",
  auto_fill: true,
};

function numOrNull(value) {
  return value === "" || value === null || value === undefined ? null : Number(value);
}

function buildInputPayload(input) {
  return { ...input, subcontract_share_percent: numOrNull(input.subcontract_share_percent) };
}

export default function App() {
  const [activeTab, setActiveTab] = useState("search");
  const [status, setStatus] = useState("Готов к демонстрации");
  const [isLoading, setIsLoading] = useState(false);

  // Поиск
  const [query, setQuery] = useState(demoQuery);
  const [searchResponse, setSearchResponse] = useState(null);
  const [selectedResult, setSelectedResult] = useState(null);

  // ТЗ
  const [templates, setTemplates] = useState([]);
  const [tzList, setTzList] = useState([]);
  const [currentTz, setCurrentTz] = useState(null);
  const [newTz, setNewTz] = useState(emptyNewTz);
  const [tzInstruction, setTzInstruction] = useState("");
  const [tzBusy, setTzBusy] = useState(false);

  // Роадмап / оценка сроков
  const [estProducts, setEstProducts] = useState([]);
  const [estProductId, setEstProductId] = useState("");
  const [estimate, setEstimate] = useState(null);

  // Аналитика и ассистент
  const [analytics, setAnalytics] = useState(null);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([{ id: "assistant-start", role: "assistant", text: "Готов помочь с ТЗ." }]);
  const [isAssistantLoading, setIsAssistantLoading] = useState(false);

  const results = searchResponse?.results?.products ?? [];
  const recommendations = searchResponse?.results?.recommendations ?? [];
  const selectedCompany = useMemo(() => selectedResult?.recommended_companies?.[0] ?? null, [selectedResult]);

  useEffect(() => {
    runSearch(demoQuery);
    loadAnalytics();
    loadTemplates();
    loadTzList();
    loadEstProducts();
  }, []);

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

  async function downloadFile(path, filename) {
    const response = await fetch(`${API_BASE}${path}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
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

  async function loadAnalytics() {
    try {
      setAnalytics(await request("/analytics/overview"));
    } catch {
      setAnalytics(null);
    }
  }

  async function loadTemplates() {
    try {
      const data = await request("/tz/templates");
      setTemplates(data.templates);
      setNewTz((current) => ({ ...current, template_key: current.template_key || data.templates[0]?.key || "" }));
    } catch (error) {
      setStatus(`Не удалось загрузить шаблоны: ${error.message}`);
    }
  }

  async function loadTzList() {
    try {
      const data = await request("/tz");
      setTzList(data.documents);
    } catch (error) {
      setStatus(`Не удалось загрузить список ТЗ: ${error.message}`);
    }
  }

  function buildCreatePayload(source, templateKey, autoFill) {
    return {
      template_key: templateKey,
      object_name: source.object_name || null,
      customer_name: source.customer_name || null,
      executor_name: source.executor_name || null,
      contract_name: source.contract_name || null,
      requisites: source.city ? { city: source.city } : {},
      input_data: buildInputPayload({
        ...emptyInput,
        object_name: source.object_name || "",
        customer_name: source.customer_name || "",
        goal: source.goal || "",
        deadline: source.deadline || "",
      }),
      auto_fill: Boolean(autoFill),
    };
  }

  async function createTz() {
    if (!newTz.template_key) return;
    setTzBusy(true);
    setStatus("Создаю ТЗ по шаблону");
    try {
      const data = await request("/tz", {
        method: "POST",
        body: JSON.stringify(buildCreatePayload(newTz, newTz.template_key, newTz.auto_fill)),
      });
      setCurrentTz(data.document);
      setActiveTab("constructor");
      setStatus(newTz.auto_fill ? "ТЗ создано и заполнено ИИ" : "ТЗ создано");
      loadTzList();
    } catch (error) {
      setStatus(`Ошибка создания ТЗ: ${error.message}`);
    } finally {
      setTzBusy(false);
    }
  }

  async function createTzFromSearch(result = selectedResult) {
    if (!result) return;
    const templateKey = templates.find((t) => t.product_id === result.product.id)?.key || "tz-universal";
    setTzBusy(true);
    setStatus("Формирую ТЗ по продукту");
    try {
      const source = { object_name: "", customer_name: emptyInput.customer_name, goal: result.product.summary, deadline: emptyInput.deadline };
      const data = await request("/tz", { method: "POST", body: JSON.stringify(buildCreatePayload(source, templateKey, true)) });
      setCurrentTz(data.document);
      setActiveTab("constructor");
      setStatus("ТЗ сформировано ИИ, проверьте разделы");
      loadTzList();
    } catch (error) {
      setStatus(`Ошибка формирования ТЗ: ${error.message}`);
    } finally {
      setTzBusy(false);
    }
  }

  async function openTz(id) {
    try {
      const data = await request(`/tz/${id}`);
      setCurrentTz(data.document);
      setActiveTab("constructor");
    } catch (error) {
      setStatus(`Не удалось открыть ТЗ: ${error.message}`);
    }
  }

  async function saveTz(silent = false) {
    if (!currentTz) return null;
    const payload = {
      title: currentTz.title,
      object_name: currentTz.object_name,
      customer_name: currentTz.customer_name,
      executor_name: currentTz.executor_name,
      contract_name: currentTz.contract_name,
      status: currentTz.status,
      input_data: buildInputPayload(currentTz.input_data),
      requisites: currentTz.requisites,
      sections: currentTz.sections.map((s) => ({ key: s.key, title: s.title, content: s.content, source: s.source })),
    };
    const data = await request(`/tz/${currentTz.id}`, { method: "PUT", body: JSON.stringify(payload) });
    setCurrentTz(data.document);
    if (!silent) {
      setStatus("ТЗ сохранено");
      loadTzList();
    }
    return data.document;
  }

  async function generateTz(mode, sectionKeys = null, instruction = tzInstruction) {
    if (!currentTz) return;
    setTzBusy(true);
    setStatus(mode === "full" ? "ИИ генерирует ТЗ целиком" : "ИИ дополняет разделы");
    try {
      await saveTz(true);
      const data = await request(`/tz/${currentTz.id}/generate`, {
        method: "POST",
        body: JSON.stringify({ mode, instruction: instruction || null, section_keys: sectionKeys }),
      });
      setCurrentTz(data.document);
      setStatus(`Готовность ТЗ: ${data.document.ready_score}%`);
      loadTzList();
    } catch (error) {
      setStatus(`Ошибка генерации: ${error.message}`);
    } finally {
      setTzBusy(false);
    }
  }

  async function switchTemplate(templateKey) {
    if (!currentTz || templateKey === currentTz.template_key) return;
    if (!window.confirm("Сменить шаблон? Текущее ТЗ будет пересобрано по новому шаблону.")) return;
    setTzBusy(true);
    setStatus("Меняю шаблон ТЗ");
    try {
      const oldId = currentTz.id;
      const source = {
        object_name: currentTz.object_name,
        customer_name: currentTz.customer_name,
        executor_name: currentTz.executor_name,
        contract_name: currentTz.contract_name,
        city: currentTz.requisites?.city || "",
        goal: currentTz.input_data?.goal || "",
        deadline: currentTz.input_data?.deadline || "",
      };
      const data = await request("/tz", { method: "POST", body: JSON.stringify(buildCreatePayload(source, templateKey, false)) });
      await request(`/tz/${oldId}`, { method: "DELETE" }).catch(() => {});
      setCurrentTz(data.document);
      setStatus("Шаблон изменён");
      loadTzList();
    } catch (error) {
      setStatus(`Ошибка смены шаблона: ${error.message}`);
    } finally {
      setTzBusy(false);
    }
  }

  async function deleteTz(id) {
    if (!window.confirm("Удалить ТЗ?")) return;
    try {
      await request(`/tz/${id}`, { method: "DELETE" });
      if (currentTz?.id === id) setCurrentTz(null);
      setStatus("ТЗ удалено");
      loadTzList();
    } catch (error) {
      setStatus(`Ошибка удаления: ${error.message}`);
    }
  }

  async function exportTz(id, title) {
    setStatus("Готовлю DOCX");
    try {
      await downloadFile(`/tz/${id}/export`, `${(title || "Техническое задание").slice(0, 60)}.docx`);
      setStatus("DOCX выгружен");
    } catch (error) {
      setStatus(`Ошибка экспорта: ${error.message}`);
    }
  }

  function updateTzField(field, value) {
    setCurrentTz((current) => ({ ...current, [field]: value }));
  }
  function updateTzInput(key, value) {
    setCurrentTz((current) => ({ ...current, input_data: { ...current.input_data, [key]: value } }));
  }
  function updateTzReq(key, value) {
    setCurrentTz((current) => ({ ...current, requisites: { ...current.requisites, [key]: value } }));
  }
  function updateSection(key, content) {
    setCurrentTz((current) => ({
      ...current,
      sections: current.sections.map((s) => (s.key === key ? { ...s, content, source: "manual" } : s)),
    }));
  }

  async function loadEstProducts() {
    try {
      const data = await request("/estimates/products");
      setEstProducts(data.products);
    } catch (error) {
      setStatus(`Не удалось загрузить продукты: ${error.message}`);
    }
  }

  async function loadEstimate(productId) {
    if (!productId) return;
    setEstProductId(productId);
    setStatus("Считаю сроки по подрядчикам");
    try {
      const data = await request(`/estimates/products/${productId}`);
      setEstimate(data);
      setStatus(`Оценка готова: ${data.summary.company_count} подрядчиков`);
    } catch (error) {
      setStatus(`Ошибка оценки: ${error.message}`);
    }
  }

  async function estimateForCurrentTz() {
    if (!currentTz) return;
    setStatus("Подбираю продукт по ТЗ и считаю сроки");
    try {
      const data = await request(`/estimates/for-tz/${currentTz.id}`, { method: "POST" });
      setActiveTab("roadmap");
      if (data.estimate) {
        setEstimate(data.estimate);
        setEstProductId(data.estimate.product_id);
        setStatus(`Подобран продукт: ${data.matched?.name ?? "—"}`);
      } else {
        setStatus("Не удалось подобрать продукт по ТЗ — выберите вручную");
      }
    } catch (error) {
      setStatus(`Ошибка оценки по ТЗ: ${error.message}`);
    }
  }

  function buildAssistantContext() {
    return {
      active_tab: activeTab,
      query,
      tz: currentTz
        ? { id: currentTz.id, template_name: currentTz.template_name, ready_score: currentTz.ready_score,
            sections_filled: currentTz.sections.filter((s) => s.content.trim()).length, sections_total: currentTz.sections.length }
        : null,
    };
  }

  function localAssistantReply(message) {
    const value = message.toLowerCase();
    if (value.includes("дополн") || value.includes("заполн")) return "Нажмите «Дополнить с ИИ» — заполню пустые разделы.";
    if (value.includes("сгенерир") || value.includes("полност")) return "Нажмите «Сгенерировать полностью» — соберу всё ТЗ.";
    if (value.includes("срок") || value.includes("роадмап") || value.includes("подряд")) return "Откройте «Роадмап» — сроки и этапы по каждому подрядчику.";
    if (value.includes("шаблон")) return "Шаблон можно сменить в конструкторе (выпадающий список).";
    return "Могу дополнить/сгенерировать ТЗ, сменить шаблон и оценить сроки подрядчиков.";
  }

  async function sendAssistantMessage(text = chatInput) {
    const message = text.trim();
    if (!message || isAssistantLoading) return;
    setChatMessages((current) => [...current, { id: `user-${Date.now()}`, role: "user", text: message }]);
    setChatInput("");
    setIsAssistantLoading(true);
    try {
      const response = await fetch(AI_CHAT_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, context: buildAssistantContext(), history: chatMessages.slice(-8) }),
      });
      if (!response.ok) throw new Error("unavailable");
      const data = await response.json();
      setChatMessages((current) => [...current, { id: `a-${Date.now()}`, role: "assistant", text: data.reply || localAssistantReply(message) }]);
    } catch {
      setChatMessages((current) => [...current, { id: `a-${Date.now()}`, role: "assistant", text: localAssistantReply(message) }]);
    } finally {
      setIsAssistantLoading(false);
    }
  }

  const tabs = [
    ["search", "Поиск"],
    ["constructor", "Конструктор ТЗ"],
    ["mytz", "Мои ТЗ"],
    ["roadmap", "Роадмап"],
    ["analytics", "Аналитика"],
  ];
  const titles = {
    search: "AI-агент поиска",
    constructor: "Конструктор ТЗ",
    mytz: "Мои ТЗ",
    roadmap: "Сроки и роадмап подрядчиков",
    analytics: "Контур управления",
  };

  return (
    <main className={`app-shell ${isChatOpen ? "chat-open" : "chat-closed"}`}>
      <aside className="sidebar">
        <section className="brand">
          <span className="eyebrow">PROSTOR MVP</span>
          <h1>Умный конструктор ТЗ</h1>
          <p>Поиск продукта, сборка ТЗ из шаблонов, ИИ-заполнение и оценка сроков подрядчиков.</p>
        </section>

        <nav className="tabs" aria-label="Разделы">
          {tabs.map(([key, label]) => (
            <button key={key} className={activeTab === key ? "active" : ""} onClick={() => setActiveTab(key)}>
              {label}
            </button>
          ))}
        </nav>

        <section className="source-card">
          <span className="eyebrow">Данные из ПРОСТОР</span>
          <dl>
            <div><dt>Компании</dt><dd>13</dd></div>
            <div><dt>Договоры</dt><dd>20</dd></div>
            <div><dt>Продукты</dt><dd>{estProducts.length || 22}</dd></div>
            <div><dt>Шаблоны ТЗ</dt><dd>{templates.length || 11}</dd></div>
            <div><dt>Сохранённых ТЗ</dt><dd>{tzList.length}</dd></div>
          </dl>
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Единый демо-поток</span>
            <h2>{titles[activeTab]}</h2>
          </div>
          <span className={`status ${isLoading || tzBusy ? "loading" : ""}`}>{status}</span>
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
            onCreateTz={createTzFromSearch}
          />
        )}

        {activeTab === "constructor" && (
          <ConstructorView
            templates={templates}
            currentTz={currentTz}
            newTz={newTz}
            setNewTz={setNewTz}
            createTz={createTz}
            tzBusy={tzBusy}
            tzInstruction={tzInstruction}
            setTzInstruction={setTzInstruction}
            onSwitchTemplate={switchTemplate}
            onGenerate={generateTz}
            onSave={saveTz}
            onExport={exportTz}
            onEstimate={estimateForCurrentTz}
            onNew={() => setCurrentTz(null)}
            updateTzField={updateTzField}
            updateTzInput={updateTzInput}
            updateTzReq={updateTzReq}
            updateSection={updateSection}
          />
        )}

        {activeTab === "mytz" && (
          <MyTzView documents={tzList} onOpen={openTz} onExport={exportTz} onDelete={deleteTz}
            onRefresh={loadTzList} onNew={() => { setCurrentTz(null); setActiveTab("constructor"); }} />
        )}

        {activeTab === "roadmap" && (
          <RoadmapView products={estProducts} productId={estProductId} estimate={estimate}
            onSelect={loadEstimate} hasTz={Boolean(currentTz)} onEstimateTz={estimateForCurrentTz} />
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
        isLoading={isAssistantLoading}
        hasTz={Boolean(currentTz)}
        onAugment={() => generateTz("augment")}
        onFull={() => generateTz("full")}
      />
    </main>
  );
}

function SearchView({ query, setQuery, runSearch, response, results, selectedResult, setSelectedResult, recommendations, onCreateTz }) {
  return (
    <div className="grid two-columns">
      <section className="panel search-panel">
        <form className="search-box" onSubmit={(e) => { e.preventDefault(); runSearch(); }}>
          <label>
            <span>Запрос пользователя</span>
            <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={4} />
          </label>
          <div className="actions">
            <button type="submit">Найти решение</button>
            <button type="button" className="secondary" onClick={() => runSearch(demoQuery)}>Демо-запрос</button>
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
            <button key={result.product.id}
              className={`result-card ${selectedResult?.product.id === result.product.id ? "selected" : ""}`}
              onClick={() => setSelectedResult(result)}>
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
              <button onClick={() => onCreateTz(selectedResult)}>Сформировать ТЗ</button>
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

function ConstructorView(props) {
  const { currentTz } = props;
  if (!currentTz) return <NewTzForm {...props} />;
  return <TzEditor {...props} />;
}

function NewTzForm({ templates, newTz, setNewTz, createTz, tzBusy }) {
  const selected = templates.find((t) => t.key === newTz.template_key);
  const set = (key, value) => setNewTz((current) => ({ ...current, [key]: value }));
  return (
    <div className="grid two-columns">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Новое ТЗ</span>
            <h3>Выберите шаблон</h3>
          </div>
          <button onClick={createTz} disabled={!newTz.template_key || tzBusy}>Создать ТЗ</button>
        </div>

        <label>
          <span>Тип / шаблон ТЗ</span>
          <select value={newTz.template_key} onChange={(e) => set("template_key", e.target.value)}>
            {templates.map((t) => <option key={t.key} value={t.key}>{t.name}</option>)}
          </select>
        </label>

        <div className="form-grid">
          <TextInput label="Объект / месторождение" value={newTz.object_name} onChange={(v) => set("object_name", v)} />
          <TextInput label="Заказчик" value={newTz.customer_name} onChange={(v) => set("customer_name", v)} />
          <TextInput label="Исполнитель" value={newTz.executor_name} onChange={(v) => set("executor_name", v)} />
          <TextInput label="Место выполнения" value={newTz.city} onChange={(v) => set("city", v)} />
          <label className="span-2">
            <span>Цель работ</span>
            <textarea value={newTz.goal} onChange={(e) => set("goal", e.target.value)} rows={3} />
          </label>
          <TextInput label="Плановый срок" type="date" value={newTz.deadline} onChange={(v) => set("deadline", v)} />
        </div>

        <div className="toggle-grid">
          <Toggle label="Сразу заполнить черновик с ИИ" checked={newTz.auto_fill} onChange={(v) => set("auto_fill", v)} />
        </div>
      </section>

      <section className="panel">
        <InfoGroup title="Описание шаблона">
          <p className="muted">{selected?.description || "Выберите шаблон, чтобы увидеть описание."}</p>
        </InfoGroup>
        <InfoGroup title="Разделов в шаблоне">
          <div className="chips"><span>{selected?.section_count ?? 0} разделов</span></div>
        </InfoGroup>
        <InfoGroup title="Все доступные шаблоны">
          <div className="chips">
            {templates.map((t) => (
              <span key={t.key} style={{ cursor: "pointer" }} onClick={() => set("template_key", t.key)}>{t.name}</span>
            ))}
          </div>
        </InfoGroup>
      </section>
    </div>
  );
}

function TzEditor({ currentTz, templates, tzBusy, tzInstruction, setTzInstruction, onSwitchTemplate,
  onGenerate, onSave, onExport, onEstimate, onNew, updateTzField, updateTzInput, updateTzReq, updateSection }) {
  const tz = currentTz;
  const readyClass = tz.ready_score >= 70 ? "good" : tz.ready_score >= 40 ? "warn" : "bad";
  const input = tz.input_data || {};
  return (
    <div className="grid draft-grid">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">ТЗ {tz.id}</span>
            <h3>{tz.template_name}</h3>
          </div>
          <div className="actions">
            <button onClick={() => onGenerate("augment")} disabled={tzBusy}>Дополнить с ИИ</button>
            <button onClick={() => onGenerate("full")} disabled={tzBusy}>Сгенерировать полностью</button>
            <button className="secondary" onClick={() => onSave()} disabled={tzBusy}>Сохранить</button>
            <button className="secondary" onClick={() => onExport(tz.id, tz.title)}>Экспорт DOCX</button>
            <button className="secondary" onClick={onEstimate}>Оценить сроки</button>
            <button className="secondary" onClick={onNew}>Новое</button>
          </div>
        </div>

        <label>
          <span>Шаблон ТЗ (можно сменить)</span>
          <select value={tz.template_key} onChange={(e) => onSwitchTemplate(e.target.value)} disabled={tzBusy}>
            {templates.map((t) => <option key={t.key} value={t.key}>{t.name}</option>)}
          </select>
        </label>

        <div className="form-grid">
          <TextInput label="Название ТЗ" value={tz.title || ""} onChange={(v) => updateTzField("title", v)} />
          <TextInput label="Объект" value={tz.object_name || ""} onChange={(v) => updateTzField("object_name", v)} />
          <TextInput label="Заказчик" value={tz.customer_name || ""} onChange={(v) => updateTzField("customer_name", v)} />
          <TextInput label="Исполнитель" value={tz.executor_name || ""} onChange={(v) => updateTzField("executor_name", v)} />
          <TextInput label="Место выполнения" value={tz.requisites?.city || ""} onChange={(v) => updateTzReq("city", v)} />
          <TextInput label="Плановый срок" type="date" value={input.deadline || ""} onChange={(v) => updateTzInput("deadline", v)} />
          <label className="span-2">
            <span>Цель работ</span>
            <textarea value={input.goal || ""} onChange={(e) => updateTzInput("goal", e.target.value)} rows={3} />
          </label>
        </div>

        <div className="toggle-grid">
          <Toggle label="Исходные данные готовы" checked={!!input.source_data_ready} onChange={(v) => updateTzInput("source_data_ready", v)} />
          <Toggle label="Нужна 3D-модель" checked={!!input.needs_3d_model} onChange={(v) => updateTzInput("needs_3d_model", v)} />
          <Toggle label="Нужен субподряд" checked={!!input.requires_subcontractor} onChange={(v) => updateTzInput("requires_subcontractor", v)} />
          <Toggle label="Отдельный РС по субподряду" checked={!!input.separate_subcontract_estimate} onChange={(v) => updateTzInput("separate_subcontract_estimate", v)} />
        </div>

        <label className="ai-instruction">
          <span>Указание для ИИ (необязательно)</span>
          <input value={tzInstruction} onChange={(e) => setTzInstruction(e.target.value)} placeholder="Напр.: сделать акцент на сроках и рисках" />
        </label>

        <div className="section-editor">
          {tz.sections.map((section) => (
            <SectionEditor key={section.key} section={section} disabled={tzBusy}
              onChange={(v) => updateSection(section.key, v)}
              onGenerate={() => onGenerate("augment", [section.key])} />
          ))}
        </div>
      </section>

      <aside className="panel inspector">
        <div className={`ready-meter ${readyClass}`}>
          <span>Готовность</span>
          <strong>{tz.ready_score}%</strong>
        </div>
        <InfoGroup title="Статус"><div className="chips"><span>{statusLabels[tz.status] || tz.status}</span></div></InfoGroup>
        <InfoGroup title="Разделы">
          <div className="chips">
            <span>{tz.sections.filter((s) => s.content.trim()).length} из {tz.sections.length} заполнено</span>
          </div>
        </InfoGroup>
        {tz.notes?.length > 0 && <ReasonList title="Заметки ИИ" items={tz.notes} />}
        <InfoGroup title="Экспорт">
          <p className="muted">Итоговый документ — единый файл DOCX (без xlsx).</p>
        </InfoGroup>
      </aside>
    </div>
  );
}

function SectionEditor({ section, onChange, onGenerate, disabled }) {
  return (
    <article className="section-card">
      <div className="section-head">
        <h5>{section.title}</h5>
        <span className={`source-badge ${section.source}`}>{sourceLabels[section.source] || section.source}</span>
      </div>
      <textarea value={section.content} onChange={(e) => onChange(e.target.value)} rows={5}
        placeholder="Текст раздела — заполните вручную или нажмите «ИИ»." />
      <div className="section-actions">
        <button type="button" className="secondary" onClick={onGenerate} disabled={disabled}>ИИ: заполнить раздел</button>
      </div>
    </article>
  );
}

function MyTzView({ documents, onOpen, onExport, onDelete, onRefresh, onNew }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Сохранённые ТЗ</span>
          <h3>Мои ТЗ ({documents.length})</h3>
        </div>
        <div className="actions">
          <button onClick={onNew}>Новое ТЗ</button>
          <button className="secondary" onClick={onRefresh}>Обновить</button>
        </div>
      </div>

      {documents.length === 0 ? (
        <EmptyState text="Пока нет сохранённых ТЗ. Создайте новое в конструкторе или из поиска." />
      ) : (
        <div className="tz-list">
          {documents.map((doc) => {
            const cls = doc.ready_score >= 70 ? "good" : doc.ready_score >= 40 ? "warn" : "bad";
            return (
              <article className="tz-card" key={doc.id}>
                <div className="tz-card-main">
                  <strong>{doc.title || doc.template_name}</strong>
                  <small>{doc.template_name}</small>
                  <div className="tz-meta">
                    <span>{doc.object_name || "объект не указан"}</span>
                    <span>{doc.customer_name || "заказчик не указан"}</span>
                    <span className={`status-badge ${cls}`}>{doc.ready_score}%</span>
                    <span>{statusLabels[doc.status] || doc.status}</span>
                  </div>
                </div>
                <div className="tz-card-actions">
                  <button onClick={() => onOpen(doc.id)}>Открыть</button>
                  <button className="secondary" onClick={() => onExport(doc.id, doc.title)}>DOCX</button>
                  <button className="secondary" onClick={() => onDelete(doc.id)}>Удалить</button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function RoadmapView({ products, productId, estimate, onSelect, hasTz, onEstimateTz }) {
  return (
    <div className="grid">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Оценка сроков</span>
            <h3>Роадмап подрядчиков</h3>
          </div>
          <div className="actions">
            <select value={productId} onChange={(e) => onSelect(e.target.value)}>
              <option value="">— выберите продукт —</option>
              {products.map((p) => (
                <option key={p.product_id} value={p.product_id}>{p.name} ({p.company_count} подр.)</option>
              ))}
            </select>
            <button className="secondary" onClick={onEstimateTz} disabled={!hasTz}>Оценить по текущему ТЗ</button>
          </div>
        </div>

        {!estimate ? (
          <EmptyState text="Выберите продукт — рассчитаю сроки и роадмап по каждому подрядчику из данных ПРОСТОР." />
        ) : (
          <>
            <div className="grid analytics-grid">
              <Metric label="Подрядчиков" value={estimate.summary.company_count} />
              <Metric label="Быстрее всех, дн" value={estimate.summary.fastest_days} />
              <Metric label="В среднем, дн" value={estimate.summary.average_days} />
              <Metric label="Дольше всех, дн" value={estimate.summary.slowest_days} />
            </div>
            <div className="section-title">
              <span className="eyebrow">Продукт</span>
              <h4>{estimate.product_name}</h4>
            </div>
            <div className="roadmap-list">
              {estimate.companies.map((company, index) => (
                <ContractorRoadmap key={company.company_id} company={company} rank={index + 1} />
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function ContractorRoadmap({ company, rank }) {
  return (
    <article className="contractor-card">
      <div className="contractor-head">
        <div>
          <strong>{rank}. {company.company_name}</strong>
          <small>
            рейтинг {company.rating ?? "—"}
            {company.contract_number ? ` · договор ${company.contract_number}` : ""}
            {company.variants > 1 ? ` · вариантов РС: ${company.variants}` : ""}
          </small>
        </div>
        <div className="contractor-est">
          <strong>{company.estimated_days} дн</strong>
          <small>~{company.estimated_months} мес · диапазон {company.min_days}–{company.max_days} дн</small>
        </div>
      </div>

      <div className="roadmap-track">
        {company.stages.map((stage, i) => (
          <div key={stage.order} className={`roadmap-seg c${i % 5}`} style={{ width: `${stage.percent}%` }}
            title={`${stage.name} — ${stage.days} дн${stage.start_date ? ` (${stage.start_date}…${stage.end_date})` : ""}`}>
            <span>{stage.days}</span>
          </div>
        ))}
      </div>

      <ol className="roadmap-stages">
        {company.stages.map((stage) => (
          <li key={stage.order}>
            <span className="rs-name">{stage.name}</span>
            <span className="rs-days">{stage.days} дн ({stage.percent}%)</span>
          </li>
        ))}
      </ol>
    </article>
  );
}

function AssistantSidebar({ isOpen, onToggle, messages, input, setInput, onSend, isLoading, hasTz, onAugment, onFull }) {
  if (!isOpen) return <button className="chat-fab" onClick={onToggle}>AI-чат</button>;

  const quickActions = [
    { label: "Дополнить ИИ", action: onAugment, disabled: !hasTz },
    { label: "Сгенерировать всё", action: onFull, disabled: !hasTz },
    { label: "Что уточнить", action: () => onSend("Что уточнить для ТЗ?") },
    { label: "Про сроки", action: () => onSend("Как оценить сроки подрядчиков?") },
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

      <div className="assistant-context">{hasTz ? "ТЗ подключено" : "ТЗ не выбрано"}</div>

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

      <form className="assistant-input" onSubmit={(e) => { e.preventDefault(); onSend(); }}>
        <textarea value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); } }}
          placeholder="Короткий запрос по ТЗ" rows={3} />
        <button type="submit" disabled={!input.trim() || isLoading}>Отправить</button>
      </form>
    </aside>
  );
}

function AnalyticsView({ analytics }) {
  if (!analytics) {
    return <section className="panel"><EmptyState text="Аналитика будет доступна после запуска backend." /></section>;
  }
  return (
    <div className="grid analytics-grid">
      <Metric label="Продукты" value={analytics.total_products} />
      <Metric label="Компании" value={analytics.total_companies} />
      <Metric label="Активные договоры" value={analytics.total_active_contracts} />
      <Metric label="Исторические кейсы" value={analytics.total_historical_cases} />
      <section className="panel span-2">
        <InfoGroup title="Популярные продукты">
          <div className="chips">{(analytics.most_requested_products || []).map((p) => <span key={p}>{p}</span>)}</div>
        </InfoGroup>
      </section>
      <section className="panel span-2">
        <ReasonList title="Частые ошибки в заявках" items={analytics.common_risk_patterns || []} />
      </section>
      <section className="panel span-2">
        <ReasonList title="Типовые этапы работ" items={analytics.common_stages || []} />
      </section>
      <section className="panel span-2">
        <ReasonList title="Кандидаты на продуктовую упаковку" items={analytics.product_packaging_candidates || []} />
      </section>
    </div>
  );
}

function TextInput({ label, value, onChange, type = "text" }) {
  return (
    <label>
      <span>{label}</span>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
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
      <ul className="reason-list">{items.map((item) => <li key={item}>{item}</li>)}</ul>
    </InfoGroup>
  );
}
