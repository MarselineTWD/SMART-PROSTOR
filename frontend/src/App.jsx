import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot, CalendarDays, CircleUserRound, Clock3, FileText,
  History, LayoutDashboard, Search, Sparkles,
} from "./icons";

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

function formatMoney(value) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(value || 0) + " ₽";
}

function computeLiveReady(tz, template) {
  const getValue = (key) => {
    if (["object_name", "customer_name", "executor_name"].includes(key)) return tz[key];
    if (key === "contract_number") return tz.contract_name;
    return tz.requisites?.[key];
  };
  const templateRequired = (template?.fields || []).filter((field) => field.required);
  const requiredValues = [tz.object_name, tz.customer_name, tz.input_data?.goal, tz.input_data?.deadline,
    ...templateRequired.filter((field) => !["object_name", "customer_name"].includes(field.key)).map((field) => getValue(field.key))];
  const filledFields = requiredValues.filter((value) => value !== null && value !== undefined && String(value).trim() !== "").length;
  const fieldRatio = requiredValues.length ? filledFields / requiredValues.length : 0;
  const sectionRatio = tz.sections?.length ? tz.sections.filter((section) => section.content.trim()).length / tz.sections.length : 0;
  const stageRatio = tz.requisites?.stages?.length ? 1 : 0;
  return Math.max(0, Math.min(100, Math.round((fieldRatio * .4 + sectionRatio * .45 + stageRatio * .15) * 100)));
}

function TemplateFields({ fields, values, onChange }) {
  const groups = fields.reduce((result, field) => {
    const group = field.group || "Основные данные";
    result[group] = [...(result[group] || []), field];
    return result;
  }, {});

  const renderField = (field) => {
    const value = values[field.key] ?? (field.input_type === "checkbox" ? false : "");
    if (field.input_type === "checkbox") {
      return <Toggle key={field.key} label={field.label} checked={Boolean(value)} onChange={(next) => onChange(field.key, next)} />;
    }
    if (field.input_type === "select") {
      return (
        <label key={field.key}>
          <span>{field.label}{field.required && <b> *</b>}</span>
          <select value={value} onChange={(event) => onChange(field.key, event.target.value)}>
            <option value="">— выберите —</option>
            {field.options.map((option) => <option key={option} value={option}>{option}</option>)}
          </select>
        </label>
      );
    }
    if (field.input_type === "textarea") {
      return (
        <label key={field.key} className="span-2">
          <span>{field.label}{field.required && <b> *</b>}</span>
          <textarea rows={3} value={value} placeholder={field.placeholder}
            onChange={(event) => onChange(field.key, event.target.value)} />
        </label>
      );
    }
    return <TextInput key={field.key} label={`${field.label}${field.required ? " *" : ""}`}
      type={field.input_type || "text"} value={value} placeholder={field.placeholder}
      onChange={(next) => onChange(field.key, next)} />;
  };

  return Object.entries(groups).map(([group, groupFields]) => (
    <details className="template-field-group span-2" key={group} open={groupFields.some((field) => field.required)}>
      <summary>
        <span>{group}</span>
        <small>{groupFields.filter((field) => field.required).length
          ? `обязательных: ${groupFields.filter((field) => field.required).length}`
          : `${groupFields.length} полей`}</small>
      </summary>
      <div className="form-grid">{groupFields.map(renderField)}</div>
    </details>
  ));
}

function ExampleDialog({ template, onClose }) {
  const example = template?.example || {};
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="example-dialog" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div><span className="eyebrow">Справка по шаблону</span><h3>{template?.name}</h3></div>
          <button className="icon-button" onClick={onClose} aria-label="Закрыть">×</button>
        </header>
        <p>{template?.description}</p>
        <dl>
          <div><dt>Пример объекта</dt><dd>{example.object_name}</dd></div>
          <div><dt>Заказчик</dt><dd>{example.customer_name}</dd></div>
          <div><dt>Цель</dt><dd>{example.goal}</dd></div>
          <div><dt>Срок</dt><dd>{example.deadline}</dd></div>
        </dl>
        <h4>Пример структуры работ</h4>
        <ol>{(example.stages || []).map((stage) => <li key={stage}>{stage}</li>)}</ol>
        <div className="example-result"><strong>Ожидаемый результат</strong><p>{example.result}</p></div>
        <button onClick={onClose}>Понятно</button>
      </section>
    </div>
  );
}

function OilGauge({ value, className }) {
  return (
    <div className={`oil-gauge ${className || ""} ${value >= 100 ? "is-full" : ""}`} aria-label={`Заполненность ТЗ ${value}%`}>
      <div className="oil-gauge-spill" aria-hidden="true"><i /><i /><i /></div>
      <div className="oil-gauge-tube">
        <div className="oil-gauge-fluid" style={{ "--oil-level": `${value}%` }}>
          <span className="oil-wave" /><i className="bubble b1" /><i className="bubble b2" /><i className="bubble b3" />
        </div>
        <div className="oil-gauge-marks">{[100, 75, 50, 25].map((mark) => <span key={mark}>{mark}</span>)}</div>
      </div>
      <strong>{value}%</strong>
      <span>Заполненность ТЗ</span>
      <small>{value === 100 ? "Готово к выпуску" : "Заполняйте поля и разделы"}</small>
    </div>
  );
}

export default function App() {
  const urlParams = new URLSearchParams(window.location.search);
  const requestedTab = urlParams.get("tab");
  const requestedTzId = urlParams.get("tz");
  const [activeTab, setActiveTab] = useState(
    ["search", "constructor", "mytz", "roadmap", "analytics"].includes(requestedTab) ? requestedTab : "search",
  );
  const [status, setStatus] = useState("Готов к демонстрации");
  const [isLoading, setIsLoading] = useState(false);

  // Поиск
  const [query, setQuery] = useState(demoQuery);
  const [searchResponse, setSearchResponse] = useState(null);
  const [selectedResult, setSelectedResult] = useState(null);

  // ТЗ
  const [templates, setTemplates] = useState([]);
  const [templateDetails, setTemplateDetails] = useState({});
  const [tzList, setTzList] = useState([]);
  const [currentTz, setCurrentTz] = useState(null);
  const [validation, setValidation] = useState(null);
  const [newTz, setNewTz] = useState(emptyNewTz);
  const [tzInstruction, setTzInstruction] = useState("");
  const [tzBusy, setTzBusy] = useState(false);

  // Роадмап / оценка сроков
  const [estProducts, setEstProducts] = useState([]);
  const [estProductId, setEstProductId] = useState("");
  const [estimate, setEstimate] = useState(null);
  const [selectedAdditionalServices, setSelectedAdditionalServices] = useState([]);

  // Аналитика и ассистент
  const [analytics, setAnalytics] = useState(null);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState(null);
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
    loadAssistantStatus();
    if (requestedTzId) openTz(requestedTzId);
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
      const details = await Promise.all(
        data.templates.map((template) => request(`/tz/templates/${template.key}`).catch(() => null)),
      );
      setTemplateDetails(Object.fromEntries(details.filter(Boolean).map((item) => [item.template.key, item.template])));
      setNewTz((current) => ({ ...current, template_key: current.template_key || data.templates[0]?.key || "" }));
    } catch (error) {
      setStatus(`Не удалось загрузить шаблоны: ${error.message}`);
    }
  }

  async function loadAssistantStatus() {
    try {
      setAssistantStatus(await request("/assistant/status"));
    } catch {
      setAssistantStatus({ enabled: false, provider: "rules", model: "offline" });
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
    const template = templateDetails[templateKey];
    const requisites = {};
    for (const field of template?.fields || []) {
      if (["object_name", "customer_name", "executor_name"].includes(field.key)) continue;
      if (field.key === "contract_number") continue;
      if (source[field.key] !== undefined && source[field.key] !== "") requisites[field.key] = source[field.key];
    }
    return {
      template_key: templateKey,
      object_name: source.object_name || null,
      customer_name: source.customer_name || null,
      executor_name: source.executor_name || null,
      contract_name: source.contract_number || source.contract_name || null,
      requisites,
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
      setValidation(data.validation);
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
      setValidation(data.validation);
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
      setValidation(data.validation);
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
    setValidation(data.validation);
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
      setValidation(data.validation);
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
      const data = await request(`/tz/${currentTz.id}/switch-template`, {
        method: "POST",
        body: JSON.stringify({ template_key: templateKey }),
      });
      setCurrentTz(data.document);
      setValidation(data.validation);
      setStatus("Шаблон изменён");
      loadTzList();
    } catch (error) {
      setStatus(`Ошибка смены шаблона: ${error.message}`);
    } finally {
      setTzBusy(false);
    }
  }

  async function validateCurrentTz() {
    if (!currentTz) return;
    setTzBusy(true);
    setStatus("Проверяю ТЗ по обязательным полям и бизнес-правилам");
    try {
      const saved = await saveTz(true);
      const result = await request(`/tz/${saved.id}/validate`, { method: "POST" });
      setValidation(result);
      setCurrentTz((current) => ({ ...current, ready_score: result.ready_score }));
      setStatus(result.valid ? "ТЗ прошло проверку" : `Найдено замечаний: ${result.issues.length}`);
    } catch (error) {
      setStatus(`Ошибка проверки ТЗ: ${error.message}`);
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

  async function loadEstimate(productId, additionalIds = []) {
    if (!productId) return;
    setEstProductId(productId);
    setSelectedAdditionalServices(additionalIds);
    setStatus("Считаю сроки и стоимость по подрядчикам");
    try {
      const query = additionalIds.map((id) => `additional_product_ids=${encodeURIComponent(id)}`).join("&");
      const data = await request(`/estimates/products/${productId}${query ? `?${query}` : ""}`);
      setEstimate(data);
      setStatus(`Оценка готова: ${data.summary.company_count} подрядчиков`);
    } catch (error) {
      setStatus(`Ошибка оценки: ${error.message}`);
    }
  }

  function toggleAdditionalService(productId) {
    const next = selectedAdditionalServices.includes(productId)
      ? selectedAdditionalServices.filter((id) => id !== productId)
      : [...selectedAdditionalServices, productId];
    loadEstimate(estProductId, next);
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
        setSelectedAdditionalServices([]);
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
      validation_issues: validation?.issues || [],
      estimate_summary: estimate?.summary || null,
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
  const tabIcons = {
    search: Search,
    constructor: FileText,
    mytz: History,
    roadmap: Clock3,
    analytics: LayoutDashboard,
  };

  return (
    <div className="platform-shell">
      <header className="platform-header">
        <button className="platform-brand" type="button" onClick={() => setActiveTab("search")}>
          <span className="platform-brand-mark"><span>П</span></span>
          <span><strong>ПРОСТОР</strong><small>единое окно заказчика</small></span>
        </button>
        <nav className="platform-nav" aria-label="Основная навигация">
          {tabs.map(([key, label]) => {
            const Icon = tabIcons[key];
            return (
              <button key={key} className={activeTab === key ? "active" : ""} onClick={() => setActiveTab(key)}>
                <Icon size={17} />{label}
              </button>
            );
          })}
        </nav>
        <div className="platform-user">
          <button className="platform-ai" type="button" onClick={() => setIsChatOpen((current) => !current)}>
            <Sparkles size={17} /> AI-помощник
          </button>
          <span className="platform-avatar"><CircleUserRound size={19} /></span>
          <span><strong>Заказчик</strong><small>рабочее пространство</small></span>
        </div>
      </header>

      <main className={`app-shell ${isChatOpen ? "chat-open" : "chat-closed"}`}>
      <aside className="sidebar">
        <section className="side-welcome">
          <span className="side-welcome-icon"><Bot size={22} /></span>
          <span className="eyebrow">Умный рабочий стол</span>
          <h1>Конструктор ТЗ</h1>
          <p>Поиск продукта, сборка ТЗ из шаблонов, ИИ-заполнение и оценка сроков подрядчиков.</p>
        </section>

        <nav className="tabs side-tabs" aria-label="Разделы">
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
            <span className="eyebrow">ПРОСТОР · единый рабочий процесс</span>
            <h2>{titles[activeTab]}</h2>
          </div>
          <div className="topbar-meta">
            <span><CalendarDays size={16} /> {new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(new Date())}</span>
            <span className={`status ${isLoading || tzBusy ? "loading" : ""}`}>{status}</span>
          </div>
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
            templateDetails={templateDetails}
            currentTz={currentTz}
            validation={validation}
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
            onValidate={validateCurrentTz}
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
            onSelect={(id) => loadEstimate(id, [])} hasTz={Boolean(currentTz)} onEstimateTz={estimateForCurrentTz}
            selectedAdditionalServices={selectedAdditionalServices} onToggleAdditional={toggleAdditionalService} />
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
        status={assistantStatus}
      />
      </main>
      <footer className="platform-footer">
        <span>ПРОСТОР · Корпоративная цифровая платформа</span>
        <span>Backend и данные подключены · DeepSeek API</span>
      </footer>
    </div>
  );
}

function SearchView({ query, setQuery, runSearch, response, results, selectedResult, setSelectedResult, recommendations, onCreateTz }) {
  return (
    <div className="grid two-columns">
      <section className="panel search-panel">
        <form className="search-box search-hero" onSubmit={(e) => { e.preventDefault(); runSearch(); }}>
          <div className="search-intro">
            <span className="eyebrow">Шаг 1</span>
            <h3>Опишите задачу своими словами</h3>
            <p>Система найдёт подходящий продукт, договоры, исполнителей и шаблон ТЗ.</p>
          </div>
          <label>
            <span>Что нужно выполнить?</span>
            <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={4} />
          </label>
          <div className="actions">
            <button type="submit">Подобрать услугу</button>
            <button type="button" className="secondary" onClick={() => { setQuery(demoQuery); runSearch(demoQuery); }}>Подставить пример</button>
          </div>
        </form>

        {response && (
          <div className="intent-line">
            <span><b>Понял задачу как:</b><small> категория запроса для подбора сценария</small></span>
            <strong>{intentLabels[response.detected_intent]}</strong>
          </div>
        )}

        <div className="result-list">
          {results.map((result) => (
            <button key={result.product.id}
              className={`result-card ${selectedResult?.product.id === result.product.id ? "selected" : ""}`}
              onClick={() => setSelectedResult(result)}>
              <span className="score">{Math.min(100, Math.round(result.score / 20 * 100))}%<small>совпадение</small></span>
              <span className="result-copy">
                <strong>{result.product.name}</strong>
                <small>{result.product.summary}</small>
                <em>{result.reasons?.slice(0, 2).join(" ")}</em>
              </span>
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

function NewTzForm({ templates, templateDetails, newTz, setNewTz, createTz, tzBusy }) {
  const selected = templateDetails[newTz.template_key] || templates.find((t) => t.key === newTz.template_key);
  const [showExample, setShowExample] = useState(false);
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

        <label className="template-select">
          <span>Тип технического задания</span>
          <select value={newTz.template_key} onChange={(event) => set("template_key", event.target.value)}>
            {templates.map((template) => <option key={template.key} value={template.key}>{template.name}</option>)}
          </select>
          <small>{selected?.description}</small>
        </label>

        <div className="form-grid">
          <TemplateFields fields={selected?.fields || []} values={newTz} onChange={set} />
          <label className="span-2">
            <span>Цель работ</span>
            <textarea value={newTz.goal} onChange={(e) => set("goal", e.target.value)} rows={3} />
          </label>
          <TextInput label="Плановый срок" type="date" value={newTz.deadline} onChange={(v) => set("deadline", v)} />
        </div>

        <div className="toggle-grid">
          <Toggle label="Сразу заполнить черновик с ИИ" checked={newTz.auto_fill} onChange={(v) => set("auto_fill", v)} />
          <button type="button" className="example-button" onClick={() => setShowExample(true)}>? Пример готового ТЗ</button>
        </div>
        {showExample && <ExampleDialog template={selected} onClose={() => setShowExample(false)} />}
      </section>

      <section className="panel">
        <InfoGroup title="Описание шаблона">
          <p className="muted">{selected?.description || "Выберите шаблон, чтобы увидеть описание."}</p>
        </InfoGroup>
        <InfoGroup title="Исходный файл">
          <div className="chips">{(selected?.source_files || []).map((file) => <span key={file}>{file}</span>)}</div>
        </InfoGroup>
        <InfoGroup title="Этапы из шаблона">
          <ol className="compact-list">{(selected?.stage_presets || []).map((stage) => <li key={stage}>{stage}</li>)}</ol>
        </InfoGroup>
        <InfoGroup title={`Структура (${selected?.sections?.length ?? selected?.section_count ?? 0})`}>
          <ol className="compact-list">{(selected?.sections || []).map((section) => <li key={section.key}>{section.title}</li>)}</ol>
        </InfoGroup>
      </section>
    </div>
  );
}

function TzEditor({ currentTz, templates, tzBusy, tzInstruction, setTzInstruction, onSwitchTemplate,
  onGenerate, onSave, onExport, onEstimate, onValidate, onNew, updateTzField, updateTzInput, updateTzReq, updateSection,
  validation, templateDetails }) {
  const tz = currentTz;
  const template = templateDetails[tz.template_key];
  const [showExample, setShowExample] = useState(false);
  const input = tz.input_data || {};
  const liveReady = computeLiveReady(tz, template);
  const readyClass = liveReady >= 70 ? "good" : liveReady >= 40 ? "warn" : "bad";
  const templateValues = {
    ...tz.requisites,
    object_name: tz.object_name || "",
    customer_name: tz.customer_name || "",
    executor_name: tz.executor_name || "",
    contract_number: tz.contract_name || "",
  };
  const setTemplateValue = (key, value) => {
    if (["object_name", "customer_name", "executor_name"].includes(key)) updateTzField(key, value);
    else if (key === "contract_number") updateTzField("contract_name", value);
    else updateTzReq(key, value);
  };
  return (
    <div className="grid draft-grid">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">ТЗ {tz.id}</span>
            <h3>{tz.template_name}</h3>
          </div>
          <div className="actions">
            <button onClick={() => onSave()} disabled={tzBusy}>Сохранить</button>
            <button className="secondary" onClick={onValidate} disabled={tzBusy}>Проверить</button>
            <button className="example-button" onClick={() => setShowExample(true)}>? Пример</button>
            <details className="action-menu">
              <summary>Действия</summary>
              <div>
                <button onClick={() => onGenerate("augment")} disabled={tzBusy}>Дополнить с DeepSeek</button>
                <button onClick={() => onGenerate("full")} disabled={tzBusy}>Пересобрать полностью</button>
                <button onClick={() => onExport(tz.id, tz.title)}>Экспорт DOCX</button>
                <button onClick={onEstimate}>Сроки и стоимость</button>
                <button onClick={onNew}>Новое ТЗ</button>
              </div>
            </details>
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
          <TemplateFields fields={template?.fields || []} values={templateValues} onChange={setTemplateValue} />
          <TextInput label="Плановый срок" type="date" value={input.deadline || ""} onChange={(v) => updateTzInput("deadline", v)} />
          <label className="span-2">
            <span>Цель работ</span>
            <textarea value={input.goal || ""} onChange={(e) => updateTzInput("goal", e.target.value)} rows={3} />
          </label>
        </div>
        {showExample && <ExampleDialog template={template} onClose={() => setShowExample(false)} />}

        <div className="toggle-grid">
          <Toggle label="Исходные данные готовы" checked={!!input.source_data_ready} onChange={(v) => updateTzInput("source_data_ready", v)} />
          <Toggle label="Нужна 3D-модель" checked={!!input.needs_3d_model} onChange={(v) => updateTzInput("needs_3d_model", v)} />
          <Toggle label="Нужен субподряд" checked={!!input.requires_subcontractor} onChange={(v) => updateTzInput("requires_subcontractor", v)} />
          <Toggle label="Отдельный РС по субподряду" checked={!!input.separate_subcontract_estimate} onChange={(v) => updateTzInput("separate_subcontract_estimate", v)} />
        </div>

        {input.requires_subcontractor && (
          <TextInput label="Доля субподряда, %" type="number" value={input.subcontract_share_percent ?? ""}
            onChange={(v) => updateTzInput("subcontract_share_percent", numOrNull(v))} />
        )}

        <StageEditor stages={tz.requisites?.stages || []} onChange={(stages) => updateTzReq("stages", stages)} />

        <details className="editor-block">
          <summary>Указание для DeepSeek</summary>
          <label className="ai-instruction">
            <span>Дополнительный контекст для генерации</span>
            <input value={tzInstruction} onChange={(e) => setTzInstruction(e.target.value)} placeholder="Напр.: сделать акцент на сроках и рисках" />
          </label>
        </details>

        <div className="section-editor">
          {tz.sections.map((section) => (
            <SectionEditor key={section.key} section={section} disabled={tzBusy}
              onChange={(v) => updateSection(section.key, v)}
              onGenerate={() => onGenerate("augment", [section.key])} />
          ))}
        </div>
      </section>

      <aside className="panel inspector">
        <OilGauge value={liveReady} className={readyClass} />
        <InfoGroup title="Статус"><div className="chips"><span>{statusLabels[tz.status] || tz.status}</span></div></InfoGroup>
        <InfoGroup title="Разделы">
          <div className="chips">
            <span>{tz.sections.filter((s) => s.content.trim()).length} из {tz.sections.length} заполнено</span>
          </div>
        </InfoGroup>
        <ValidationPanel validation={validation} />
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
    <details className="section-card" open={!section.content.trim()}>
      <summary className="section-head">
        <h5>{section.title}</h5>
        <span className={`source-badge ${section.source}`}>{sourceLabels[section.source] || section.source}</span>
      </summary>
      <textarea value={section.content} onChange={(e) => onChange(e.target.value)} rows={6}
        placeholder="Текст раздела — заполните вручную или используйте DeepSeek." />
      <div className="section-actions">
        <button type="button" className="secondary" onClick={onGenerate} disabled={disabled}>Заполнить раздел</button>
      </div>
    </details>
  );
}

function StageEditor({ stages, onChange }) {
  const update = (index, value) => onChange(stages.map((stage, i) => (i === index ? value : stage)));
  return (
    <details className="editor-block">
      <summary>Этапы и календарный план ({stages.length})</summary>
      <div className="stage-editor">
        {stages.map((stage, index) => (
          <div key={`${index}-${stage}`}>
            <span>{index + 1}</span>
            <input value={stage} onChange={(event) => update(index, event.target.value)} />
            <button type="button" className="icon-button" onClick={() => onChange(stages.filter((_, i) => i !== index))}>×</button>
          </div>
        ))}
        <button type="button" className="secondary" onClick={() => onChange([...stages, "Новый этап"])}>Добавить этап</button>
      </div>
    </details>
  );
}

function ValidationPanel({ validation }) {
  if (!validation) return null;
  const issues = validation.issues || [];
  return (
    <InfoGroup title="Проверка ТЗ">
      <div className={`validation-summary ${validation.valid ? "valid" : "invalid"}`}>
        <strong>{validation.valid ? "Проверка пройдена" : `${issues.length} замечаний`}</strong>
        <span>{validation.issue_counts?.high || 0} критичных · {validation.issue_counts?.medium || 0} средних</span>
      </div>
      {issues.length > 0 && (
        <div className="validation-list">
          {issues.slice(0, 8).map((issue) => (
            <article key={issue.code} className={`validation-item ${issue.severity}`}>
              <strong>{issue.title}</strong>
              <p>{issue.message}</p>
              <small>{issue.recommendation}</small>
            </article>
          ))}
        </div>
      )}
    </InfoGroup>
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

function RoadmapView({ products, productId, estimate, onSelect, hasTz, onEstimateTz,
  selectedAdditionalServices, onToggleAdditional }) {
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
              <Metric label="Минимальная стоимость" value={formatMoney(estimate.summary.lowest_cost_without_vat)} />
              <Metric label="Средняя стоимость" value={formatMoney(estimate.summary.average_cost_without_vat)} />
              <Metric label="Быстрее всех" value={`${estimate.summary.fastest_days} дн`} />
            </div>
            <div className="section-title">
              <span className="eyebrow">Продукт</span>
              <h4>{estimate.product_name}</h4>
            </div>
            <p className="estimate-disclaimer">{estimate.summary.cost_disclaimer}</p>
            {estimate.available_additional_services?.length > 0 && (
              <details className="additional-services" open>
                <summary>Дополнительные услуги из договоров ПРОСТОР</summary>
                <p>Добавьте связанные работы — стоимость каждого подрядчика пересчитается автоматически.</p>
                <div className="additional-service-grid">
                  {estimate.available_additional_services.map((service) => (
                    <label key={service.product_id} className={selectedAdditionalServices.includes(service.product_id) ? "selected" : ""}>
                      <input type="checkbox" checked={selectedAdditionalServices.includes(service.product_id)}
                        onChange={() => onToggleAdditional(service.product_id)} />
                      <span>
                        <strong>{service.name}</strong>
                        <small>{service.common_company_count} подрядчиков · от {formatMoney(service.min_cost_without_vat)}</small>
                      </span>
                    </label>
                  ))}
                </div>
              </details>
            )}
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
          <strong>{formatMoney(company.cost_without_vat)}</strong>
          <small>без НДС · {company.estimated_days} дн · с НДС {formatMoney(company.cost_with_vat)}</small>
          {company.additional_cost_without_vat > 0 && <small>допработы: +{formatMoney(company.additional_cost_without_vat)}</small>}
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
            <span className="rs-days">{stage.days} дн · {formatMoney(stage.estimated_cost_without_vat)}</span>
          </li>
        ))}
      </ol>
      {company.additional_services?.length > 0 && (
        <div className="contractor-addons">
          {company.additional_services.map((service) => (
            <span key={service.product_id}>{service.name}: +{formatMoney(service.cost_without_vat)}</span>
          ))}
        </div>
      )}
    </article>
  );
}

function AssistantSidebar({ isOpen, onToggle, messages, input, setInput, onSend, isLoading, hasTz, onAugment, onFull, status }) {
  const messageListRef = useRef(null);

  useEffect(() => {
    if (!isOpen || !messageListRef.current) return;
    messageListRef.current.scrollTo({
      top: messageListRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, isLoading, isOpen]);

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
          <small className={`provider-status ${status?.enabled ? "online" : "offline"}`}>
            {status?.enabled ? `DeepSeek · ${status.model}` : "Локальные правила"}
          </small>
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

      <div className="message-list" ref={messageListRef}>
        {messages.map((message) => (
          <div className={`message ${message.role}`} key={message.id}>{message.text}</div>
        ))}
        {isLoading && <div className="message assistant message-loading" aria-label="ИИ готовит ответ"><i /><i /><i /></div>}
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

function TextInput({ label, value, onChange, type = "text", placeholder = "" }) {
  return (
    <label>
      <span>{label}</span>
      <input type={type} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
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

function EmptyState({ text }) {
  return <p className="empty-state">{text}</p>;
}
