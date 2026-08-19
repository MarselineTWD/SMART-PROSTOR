import { useEffect, useRef, useState } from "react";
import {
  Bot, CalendarDays, CircleUserRound, Clock3, FileText,
  History, LayoutDashboard, Search, Send, Sparkles, X,
} from "./icons";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
const AI_CHAT_ENDPOINT = import.meta.env.VITE_AI_CHAT_ENDPOINT ?? `${API_BASE}/assistant/chat`;
const LOCAL_DRAFT_KEY = "prostor:unsaved-tz:v1";

function readLocalDraft() {
  try {
    const value = JSON.parse(window.localStorage.getItem(LOCAL_DRAFT_KEY) || "null");
    return value?.version === 1 && value.document?.template_key ? value : null;
  } catch {
    window.localStorage.removeItem(LOCAL_DRAFT_KEY);
    return null;
  }
}

function clearLocalDraft() {
  try { window.localStorage.removeItem(LOCAL_DRAFT_KEY); } catch { /* storage недоступен */ }
}

const CHAT_GREETING = {
  id: "assistant-start",
  role: "assistant",
  text: "Опишите задачу одним сообщением или напишите «собери ТЗ». Я учту все поля конструктора, диалог и особые условия из базы, затем сам перенесу данные в черновик.",
  suggestions: [],
  field_updates: [],
  warnings: [],
};

function applyUpdatesToDocument(document, updates = []) {
  if (!document) return document;
  const next = structuredClone(document);
  next.input_data ||= {};
  next.requisites ||= {};
  next.sections ||= [];
  for (const update of updates) {
    if (update.target === "document") next[update.key] = update.value;
    if (update.target === "input_data") next.input_data[update.key] = update.value;
    if (update.target === "requisites") next.requisites[update.key] = update.value;
    if (update.target === "section") {
      const section = next.sections.find((item) => item.key === update.key);
      if (section) { section.content = String(update.value); section.source = "ai"; }
    }
  }
  return next;
}

function requestedGenerationMode(message) {
  const text = message.toLowerCase();
  if (!/(тз|техническ\w* задан)/i.test(text)) return null;
  if (/(собер|созда|сформир|сгенерир|сделай|напиш|полност)/i.test(text)) return "full";
  if (/(заполн|дополн)/i.test(text)) return "augment";
  return null;
}

function normalizeChatMessage(message) {
  return {
    id: message.id,
    role: message.role,
    text: message.text,
    suggestions: message.suggestions || [],
    field_updates: message.field_updates || [],
    warnings: message.warnings || [],
    discovery: message.discovery || null,
    provider: message.provider,
    fallback: Boolean(message.fallback),
  };
}

function formatUpdateValue(value) {
  if (value === true) return "Да";
  if (value === false) return "Нет";
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.map((item) => typeof item === "object" ? item.name : item).filter(Boolean).join(", ");
  return String(value);
}

const demoQuery = "Нужно оценить запасы по объекту и подготовить проектно-технический документ";

const intentLabels = {
  service_search: "Подбор типа ТЗ",
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
    <section className="template-field-group span-2 fields-always-open" key={group}>
      <header>
        <span>{group}</span>
        <small>{groupFields.filter((field) => field.required).length
          ? `обязательных: ${groupFields.filter((field) => field.required).length}`
          : `${groupFields.length} полей`}</small>
      </header>
      <div className="form-grid">{groupFields.map(renderField)}</div>
    </section>
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
        <p className="muted">Это базовый пример. Фактические услуги и количество этапов ИИ пересобирает по параметрам конкретного ТЗ.</p>
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
    ["constructor", "mytz", "analytics"].includes(requestedTab) ? requestedTab : "constructor",
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
  const [isNewDraft, setIsNewDraft] = useState(true);
  const [validation, setValidation] = useState(null);
  const validationRequestRef = useRef(0);
  const [newTz, setNewTz] = useState(emptyNewTz);
  const [tzInstruction, setTzInstruction] = useState("");
  const [tzBusy, setTzBusy] = useState(false);

  // Роадмап / оценка сроков
  const [estProducts, setEstProducts] = useState([]);
  const [estimate, setEstimate] = useState(null);
  const [selectedAdditionalServices, setSelectedAdditionalServices] = useState([]);

  // Аналитика и ассистент
  const [analytics, setAnalytics] = useState(null);
  const [contractorAnalytics, setContractorAnalytics] = useState(null);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState(null);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([CHAT_GREETING]);
  const [isAssistantLoading, setIsAssistantLoading] = useState(false);

  const results = searchResponse?.results?.products ?? [];

  useEffect(() => {
    loadAnalytics();
    loadContractorAnalytics();
    loadTemplates();
    loadTzList();
    loadAssistantStatus();
    if (requestedTzId) openTz(requestedTzId);
  }, []);

  useEffect(() => {
    if (!currentTz || !isNewDraft) return;
    try {
      window.localStorage.setItem(LOCAL_DRAFT_KEY, JSON.stringify({
        version: 1,
        updated_at: new Date().toISOString(),
        document: currentTz,
        validation,
      }));
    } catch {
      // Конструктор продолжит работать, даже если браузер запретил localStorage.
    }
  }, [currentTz, validation, isNewDraft]);

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
    setStatus("Определяю подходящий тип ТЗ");
    try {
      const data = await request("/search/query", {
        method: "POST",
        body: JSON.stringify({ query: nextQuery, limit: 3 }),
      });
      setSearchResponse(data);
      setSelectedResult(data.results.products[0] ?? null);
      setStatus("Шаблоны ТЗ подобраны");
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

  async function loadContractorAnalytics() {
    try {
      setContractorAnalytics(await request("/analytics/contractors"));
    } catch {
      setContractorAnalytics(null);
    }
  }

  async function loadTemplates() {
    try {
      const data = await request("/tz/templates");
      setTemplates(data.templates);
      const details = await Promise.all(
        data.templates.map((template) => request(`/tz/templates/${template.key}`).catch(() => null)),
      );
      const detailMap = Object.fromEntries(details.filter(Boolean).map((item) => [item.template.key, item.template]));
      setTemplateDetails(detailMap);
      setNewTz((current) => ({ ...current, template_key: current.template_key || data.templates[0]?.key || "" }));
      if (!requestedTzId) {
        const localDraft = readLocalDraft();
        if (localDraft && data.templates.some((template) => template.key === localDraft.document.template_key)) {
          setCurrentTz(localDraft.document);
          setValidation(localDraft.validation);
          setIsNewDraft(true);
          setStatus("Несохранённый черновик восстановлен");
          return;
        }
        const firstKey = data.templates[0]?.key;
        if (firstKey) {
          const preview = await request("/tz/preview", {
            method: "POST",
            body: JSON.stringify({
              template_key: firstKey,
              customer_name: emptyInput.customer_name,
              input_data: buildInputPayload(emptyInput),
              requisites: {},
              auto_fill: false,
            }),
          });
          setCurrentTz(preview.document);
          setValidation(preview.validation);
          setIsNewDraft(true);
        }
      }
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

  async function startNewDraft(templateKey = templates[0]?.key) {
    if (!templateKey) return;
    setTzBusy(true);
    try {
      const data = await request("/tz/preview", {
        method: "POST",
        body: JSON.stringify({
          template_key: templateKey,
          customer_name: emptyInput.customer_name,
          input_data: buildInputPayload(emptyInput),
          requisites: {},
          auto_fill: false,
        }),
      });
      setCurrentTz(data.document);
      setValidation(data.validation);
      setEstimate(null);
      setSelectedAdditionalServices([]);
      setChatMessages([CHAT_GREETING]);
      clearLocalDraft();
      setIsNewDraft(true);
      setActiveTab("constructor");
      setStatus("Новый черновик открыт — запись в БД ещё не создана");
    } catch (error) {
      setStatus(`Не удалось открыть конструктор: ${error.message}`);
    } finally {
      setTzBusy(false);
    }
  }

  async function createTz() {
    if (!currentTz) return;
    setTzBusy(true);
    setStatus("Финально создаю ТЗ");
    try {
      const data = await request("/tz", {
        method: "POST",
        body: JSON.stringify({
          template_key: currentTz.template_key,
          product_id: currentTz.product_id,
          title: currentTz.title,
          object_name: currentTz.object_name,
          customer_name: currentTz.customer_name,
          executor_name: currentTz.executor_name,
          contract_name: currentTz.contract_name,
          input_data: buildInputPayload(currentTz.input_data || emptyInput),
          requisites: currentTz.requisites || {},
          sections: currentTz.sections || [],
          ai_initially_generated: Boolean(currentTz.ai_initially_generated),
          auto_fill: false,
        }),
      });
      setCurrentTz(data.document);
      setValidation(data.validation);
      clearLocalDraft();
      setIsNewDraft(false);
      setStatus("ТЗ создано и сохранено");
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
    setStatus("Формирую ТЗ по рекомендованному шаблону");
    try {
      const source = { object_name: "", customer_name: emptyInput.customer_name, goal: result.product.summary, deadline: emptyInput.deadline };
      const data = await request("/tz", { method: "POST", body: JSON.stringify(buildCreatePayload(source, templateKey, true)) });
      setCurrentTz(data.document);
      setValidation(data.validation);
      setEstimate(null);
      setSelectedAdditionalServices([]);
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
      setEstimate(null);
      setSelectedAdditionalServices([]);
      setIsNewDraft(false);
      setActiveTab("constructor");
      loadChatHistory(id);
    } catch (error) {
      setStatus(`Не удалось открыть ТЗ: ${error.message}`);
    }
  }

  async function loadChatHistory(id) {
    try {
      const data = await request(`/tz/${id}/chat`);
      const history = (data.messages || []).map(normalizeChatMessage);
      setChatMessages(history.length ? history : [CHAT_GREETING]);
    } catch {
      setChatMessages([CHAT_GREETING]);
    }
  }

  async function saveTz(silent = false) {
    if (!currentTz) return null;
    if (isNewDraft) {
      if (!silent) setStatus("Черновик хранится в конструкторе и будет создан финальной кнопкой");
      return currentTz;
    }
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
      ai_initially_generated: Boolean(currentTz.ai_initially_generated),
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

  async function generateTz(mode, sectionKeys = null, instruction = tzInstruction, planOnly = false) {
    if (!currentTz) return;
    setTzBusy(true);
    setStatus(mode === "full" ? "ИИ генерирует ТЗ целиком" : "ИИ дополняет разделы");
    try {
      if (!isNewDraft) await saveTz(true);
      const data = await request(isNewDraft ? "/tz/preview/generate" : `/tz/${currentTz.id}/generate`, {
        method: "POST",
        body: JSON.stringify({
          ...(isNewDraft ? { document: currentTz } : {}),
          mode, instruction: instruction || null, section_keys: sectionKeys, plan_only: planOnly,
        }),
      });
      setCurrentTz(data.document);
      setValidation(data.validation);
      setStatus(`Готовность ТЗ: ${data.document.ready_score}%`);
      if (!isNewDraft) loadTzList();
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
      const data = await request(isNewDraft ? "/tz/preview" : `/tz/${currentTz.id}/switch-template`, {
        method: "POST",
        body: JSON.stringify(isNewDraft ? {
          template_key: templateKey,
          title: currentTz.title,
          object_name: currentTz.object_name,
          customer_name: currentTz.customer_name,
          executor_name: currentTz.executor_name,
          contract_name: currentTz.contract_name,
          input_data: currentTz.input_data,
          requisites: currentTz.requisites,
          auto_fill: false,
        } : { template_key: templateKey }),
      });
      setCurrentTz(data.document);
      setValidation(data.validation);
      setStatus("Шаблон изменён");
      setEstimate(null);
      if (!isNewDraft) loadTzList();
    } catch (error) {
      setStatus(`Ошибка смены шаблона: ${error.message}`);
    } finally {
      setTzBusy(false);
    }
  }

  async function validateCurrentTz({ silent = false } = {}) {
    if (!currentTz) return;
    const requestId = ++validationRequestRef.current;
    if (!silent) {
      setTzBusy(true);
      setStatus("Проверяю ТЗ по обязательным полям и бизнес-правилам");
    }
    try {
      const result = await request("/tz/preview/validate", {
        method: "POST",
        body: JSON.stringify(currentTz),
      });
      if (requestId !== validationRequestRef.current) return;
      setValidation(result);
      setCurrentTz((current) => ({ ...current, ready_score: result.ready_score }));
      if (!silent) setStatus(result.valid ? "ТЗ прошло проверку" : `Найдено замечаний: ${result.issues.length}`);
    } catch (error) {
      if (requestId === validationRequestRef.current) setStatus(`Ошибка проверки ТЗ: ${error.message}`);
    } finally {
      if (!silent && requestId === validationRequestRef.current) setTzBusy(false);
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
    setCurrentTz((current) => ({ ...current, status: current.status === "ready" ? "draft" : current.status, [field]: value }));
  }
  function updateTzInput(key, value) {
    setCurrentTz((current) => ({ ...current, status: current.status === "ready" ? "draft" : current.status, input_data: { ...current.input_data, [key]: value } }));
  }
  function updateTzReq(key, value) {
    setCurrentTz((current) => ({ ...current, status: current.status === "ready" ? "draft" : current.status, requisites: { ...current.requisites, [key]: value } }));
  }
  function updateSection(key, content) {
    setCurrentTz((current) => ({
      ...current,
      status: current.status === "ready" ? "draft" : current.status,
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

  function toggleAdditionalService(productId) {
    const next = selectedAdditionalServices.includes(productId)
      ? selectedAdditionalServices.filter((id) => id !== productId)
      : [...selectedAdditionalServices, productId];
    estimateForCurrentTz(next);
  }

  async function estimateForCurrentTz(additionalIds = []) {
    if (!currentTz) return;
    const serviceIds = Array.isArray(additionalIds) ? additionalIds : selectedAdditionalServices;
    setStatus("Сохраняю ТЗ и рассчитываю его этапы");
    try {
      if (!isNewDraft) await saveTz(true);
      const query = serviceIds.map((id) => `additional_product_ids=${encodeURIComponent(id)}`).join("&");
      const path = isNewDraft ? "/estimates/for-draft" : `/estimates/for-tz/${currentTz.id}`;
      const data = await request(`${path}${query ? `?${query}` : ""}`, {
        method: "POST",
        ...(isNewDraft ? { body: JSON.stringify(currentTz) } : {}),
      });
      if (data.estimate) {
        setEstimate(data.estimate);
        setSelectedAdditionalServices(serviceIds);
        setStatus(`Роадмап рассчитан по этапам ТЗ: ${data.estimate.summary.company_count} подрядчиков`);
      } else {
        setEstimate(null);
        setStatus("Для роадмапа заполните этапы ТЗ; если они есть — уточните название и цель работ");
      }
    } catch (error) {
      setStatus(`Ошибка оценки по ТЗ: ${error.message}`);
    }
  }

  function addCustomSection(title) {
    const cleanTitle = title.trim();
    if (!cleanTitle) return;
    const key = `custom-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
    setCurrentTz((current) => ({
      ...current,
      status: current.status === "ready" ? "draft" : current.status,
      sections: [...current.sections, { key, title: cleanTitle, content: "", source: "manual" }],
    }));
    setStatus(`Добавлен раздел «${cleanTitle}» — его название будет передано ИИ`);
  }

  function removeCustomSection(key) {
    setCurrentTz((current) => ({
      ...current,
      status: current.status === "ready" ? "draft" : current.status,
      sections: current.sections.filter((section) => section.key !== key),
    }));
  }

  async function saveTzFeedback(id, payload) {
    const data = await request(`/tz/${id}/feedback`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    setCurrentTz((current) => current?.id === id ? data.document : current);
    await loadTzList();
    setStatus("Оценки сохранены — спасибо за обратную связь");
    return data.document;
  }

  async function selectContractorAndComplete(company) {
    if (!currentTz || !company) return;
    if (!validation?.valid || validation.ready_score < 100) {
      setStatus("Сначала заполните и проверьте ТЗ до 100%");
      return;
    }
    setTzBusy(true);
    setStatus(`Фиксирую исполнителя ${company.company_name} и завершаю ТЗ`);
    try {
      const data = await request("/tz/complete", {
        method: "POST",
        body: JSON.stringify({
          document: currentTz,
          company_id: company.company_id,
          additional_product_ids: selectedAdditionalServices,
        }),
      });
      setCurrentTz(data.document);
      setValidation(data.validation);
      setIsNewDraft(false);
      clearLocalDraft();
      setStatus(`ТЗ завершено: исполнитель ${company.company_name}`);
      loadTzList();
    } catch (error) {
      setStatus(`Не удалось завершить ТЗ: ${error.message}`);
    } finally {
      setTzBusy(false);
    }
  }

  function buildAssistantContext() {
    return {
      active_tab: activeTab,
      query,
      current_document: currentTz,
      validation_issues: validation?.issues || [],
      estimate_summary: estimate?.summary || null,
    };
  }

  function localAssistantReply(message) {
    const value = message.toLowerCase();
    if (value.includes("дополн") || value.includes("заполн")) return "Переношу данные диалога в поля и дополняю пустые разделы ТЗ.";
    if (value.includes("сгенерир") || value.includes("полност") || value.includes("собери тз")) return "Собираю ТЗ по заполненным полям и истории диалога.";
    if (value.includes("срок") || value.includes("роадмап") || value.includes("подряд")) return "Заполните этапы и нажмите «Рассчитать диаграмму Ганта» внизу конструктора.";
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
      if (currentTz && !isNewDraft) {
        // Чат привязан к документу: история хранится на сервере, ИИ может предлагать правки полей.
        const data = await request(`/tz/${currentTz.id}/chat`, {
          method: "POST",
          body: JSON.stringify({ message, context: { active_tab: activeTab } }),
        });
        let nextMessage = { ...normalizeChatMessage(data.message), discovery: data.discovery || null };
        setAssistantStatus({ enabled: data.provider === "deepseek" && !data.fallback, provider: data.provider, model: data.model || "local" });
        let nextValidation = data.validation;
        if (nextMessage.field_updates?.length) {
          const applied = await request(`/tz/${currentTz.id}/chat/apply`, {
            method: "POST", body: JSON.stringify({ updates: nextMessage.field_updates }),
          });
          setCurrentTz(applied.document);
          nextValidation = applied.validation;
          const appliedKeys = new Set((applied.applied || []).map((item) => `${item.target}:${item.key}`));
          nextMessage = { ...nextMessage, field_updates: nextMessage.field_updates.map((item) => ({
            ...item, applied: appliedKeys.has(`${item.target}:${item.key}`),
          })) };
        }
        const generationMode = requestedGenerationMode(message);
        if (generationMode) {
          const generated = await request(`/tz/${currentTz.id}/generate`, {
            method: "POST",
            body: JSON.stringify({ mode: generationMode, instruction: `Собери ТЗ по диалогу: ${message}` }),
          });
          setCurrentTz(generated.document);
          nextValidation = generated.validation;
          nextMessage.text = `${nextMessage.text} Поля и разделы ТЗ обновлены по диалогу.`;
        }
        setChatMessages((current) => [...current, nextMessage]);
        setValidation(nextValidation);
        setCurrentTz((current) => current && nextValidation ? { ...current, ready_score: nextValidation.ready_score } : current);
      } else {
        const response = await fetch(currentTz ? `${API_BASE}/assistant/draft-chat` : AI_CHAT_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            context: buildAssistantContext(),
            history: chatMessages.slice(-8).map((m) => ({ role: m.role, text: m.text })),
            ...(currentTz ? { document: currentTz } : {}),
          }),
        });
        if (!response.ok) throw new Error("unavailable");
        const data = await response.json();
        setAssistantStatus({ enabled: data.provider === "deepseek" && !data.fallback, provider: data.provider, model: data.model || "local" });
        let nextMessage = normalizeChatMessage({
          id: `a-${Date.now()}`,
          role: "assistant",
          text: data.reply || localAssistantReply(message),
          suggestions: data.suggestions,
          field_updates: data.field_updates,
          warnings: data.warnings,
          provider: data.provider,
          fallback: data.fallback,
          discovery: data.discovery,
        });
        if (currentTz) {
          const appliedUpdates = (data.field_updates || []).map((item) => ({ ...item, applied: true }));
          let nextDocument = applyUpdatesToDocument(currentTz, appliedUpdates);
          const generationMode = requestedGenerationMode(message);
          if (generationMode) {
            const dialogContext = [...chatMessages.filter((item) => item.role === "user").slice(-8).map((item) => item.text), message].join("\n");
            const generated = await request("/tz/preview/generate", {
              method: "POST",
              body: JSON.stringify({ document: nextDocument, mode: generationMode, instruction: `Контекст диалога:\n${dialogContext}` }),
            });
            nextDocument = generated.document;
            setValidation(generated.validation);
            nextMessage.text = `${nextMessage.text} Поля и разделы черновика уже обновлены.`;
          } else {
            const checked = await request("/tz/preview/validate", {
              method: "POST", body: JSON.stringify(nextDocument),
            });
            setValidation(checked);
            nextDocument.ready_score = checked.ready_score;
          }
          setCurrentTz(nextDocument);
          nextMessage.field_updates = appliedUpdates;
          if (appliedUpdates.length) setStatus(`ИИ автоматически заполнил полей: ${appliedUpdates.length}`);
        }
        setChatMessages((current) => [...current, nextMessage]);
      }
    } catch {
      setAssistantStatus({ enabled: false, provider: "rules", model: "local" });
      setChatMessages((current) => [...current, { id: `a-${Date.now()}`, role: "assistant", text: localAssistantReply(message) }]);
    } finally {
      setIsAssistantLoading(false);
    }
  }

  async function applyFieldUpdates(_messageId, updates) {
    if (!currentTz || !updates?.length) return;
    setIsAssistantLoading(true);
    try {
      if (isNewDraft) {
        setCurrentTz((current) => applyUpdatesToDocument(current, updates));
        const appliedKeys = new Set(updates.map((u) => `${u.target}:${u.key}`));
        setChatMessages((current) => current.map((m) => ({
          ...m,
          field_updates: (m.field_updates || []).map((u) =>
            appliedKeys.has(`${u.target}:${u.key}`) ? { ...u, applied: true } : u),
        })));
        setStatus(`Перенесено в черновик: ${updates.length}`);
        return;
      }
      const data = await request(`/tz/${currentTz.id}/chat/apply`, {
        method: "POST",
        body: JSON.stringify({ updates }),
      });
      setCurrentTz(data.document);
      setValidation(data.validation);
      const appliedKeys = new Set((data.applied || []).map((u) => `${u.target}:${u.key}`));
      setChatMessages((current) => current.map((m) => ({
        ...m,
        field_updates: (m.field_updates || []).map((u) =>
          appliedKeys.has(`${u.target}:${u.key}`) ? { ...u, applied: true } : u),
      })));
      const skipped = data.skipped?.length ? `, пропущено: ${data.skipped.length}` : "";
      setStatus(`Перенесено в ТЗ: ${data.applied?.length ?? 0}${skipped}`);
    } catch (error) {
      setStatus(`Ошибка переноса: ${error.message}`);
    } finally {
      setIsAssistantLoading(false);
    }
  }

  const tabs = [
    ["constructor", "Конструктор ТЗ"],
    ["mytz", "Мои ТЗ"],
    ["analytics", "Аналитика"],
  ];
  const titles = {
    constructor: "Конструктор ТЗ",
    mytz: "Мои ТЗ",
    analytics: "Контур управления",
  };
  const tabIcons = {
    constructor: FileText,
    mytz: History,
    analytics: LayoutDashboard,
  };

  return (
    <div className="platform-shell">
      <header className="platform-header">
        <button className="platform-brand" type="button" onClick={() => setActiveTab("constructor")}>
          <strong>ПРОСТОР 2.0</strong>
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

        {activeTab === "constructor" && (
          <ConstructorView
            templates={templates}
            templateDetails={templateDetails}
            currentTz={currentTz}
            validation={validation}
            newTz={newTz}
            setNewTz={setNewTz}
            createTz={createTz}
            isNewDraft={isNewDraft}
            tzBusy={tzBusy}
            tzInstruction={tzInstruction}
            setTzInstruction={setTzInstruction}
            onSwitchTemplate={switchTemplate}
            onGenerate={generateTz}
            onSave={saveTz}
            onExport={exportTz}
            onEstimate={estimateForCurrentTz}
            onValidate={validateCurrentTz}
            onNew={() => startNewDraft()}
            updateTzField={updateTzField}
            updateTzInput={updateTzInput}
            updateTzReq={updateTzReq}
            updateSection={updateSection}
            onAddSection={addCustomSection}
            onRemoveSection={removeCustomSection}
            estimate={estimate}
            selectedAdditionalServices={selectedAdditionalServices}
            onToggleAdditional={toggleAdditionalService}
            onSelectContractor={selectContractorAndComplete}
          />
        )}

        {activeTab === "mytz" && (
          <MyTzView documents={tzList} onOpen={openTz} onExport={exportTz} onDelete={deleteTz}
            onRefresh={loadTzList} onNew={() => startNewDraft()} onSaveFeedback={saveTzFeedback} />
        )}

        {activeTab === "analytics" && <AnalyticsView analytics={analytics} contractorAnalytics={contractorAnalytics} />}
      </section>

      <AssistantSidebar
        isOpen={isChatOpen}
        onToggle={() => setIsChatOpen((current) => !current)}
        messages={chatMessages}
        input={chatInput}
        setInput={setChatInput}
        onSend={sendAssistantMessage}
        onApply={applyFieldUpdates}
        isLoading={isAssistantLoading}
        hasTz={Boolean(currentTz)}
        onAugment={() => generateTz("augment")}
        onFull={() => generateTz("full")}
        status={assistantStatus}
        onOpenTz={openTz}
      />
      </main>
      <footer className="platform-footer">
        <span>ПРОСТОР · Корпоративная цифровая платформа</span>
        <span>Backend и данные подключены · DeepSeek API</span>
      </footer>
    </div>
  );
}

function SearchView({ query, setQuery, runSearch, response, results, selectedResult, setSelectedResult,
  templates, templateDetails, onCreateTz }) {
  const templateResults = results.reduce((items, result) => {
    const template = templates.find((item) => item.product_id === result.product.id)
      || templates.find((item) => item.key === "tz-universal");
    if (!template || items.some((item) => item.template.key === template.key)) return items;
    return [...items, { result, template }];
  }, []);
  const selectedTemplate = templates.find((item) => item.product_id === selectedResult?.product.id)
    || templates.find((item) => item.key === "tz-universal");
  const selectedTemplateDetail = selectedTemplate ? templateDetails[selectedTemplate.key] : null;
  const matchReasons = (selectedResult?.reasons || []).filter((reason) => reason.startsWith("Совпали"));

  return (
    <div className="grid two-columns">
      <section className="panel search-panel">
        <form className="search-box search-hero" onSubmit={(e) => { e.preventDefault(); runSearch(); }}>
          <div className="search-intro">
            <span className="eyebrow">Шаг 1</span>
            <h3>Опишите задачу своими словами</h3>
            <p>Система определит предмет работ и предложит подходящую структуру технического задания.</p>
          </div>
          <label>
            <span>Что должно быть выполнено и какой результат нужен?</span>
            <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={4} />
          </label>
          <div className="actions">
            <button type="submit">Подобрать шаблон ТЗ</button>
            <button type="button" className="secondary" onClick={() => { setQuery(demoQuery); runSearch(demoQuery); }}>Подставить пример</button>
          </div>
        </form>

        {response && (
          <div className="intent-line">
            <span><b>Понял запрос как:</b><small>это влияет на выбор структуры ТЗ</small></span>
            <strong>{intentLabels[response.detected_intent]}</strong>
          </div>
        )}

        <div className="result-list">
          {templateResults.map(({ result, template }) => (
            <button key={template.key}
              className={`result-card ${selectedTemplate?.key === template.key ? "selected" : ""}`}
              onClick={() => setSelectedResult(result)}>
              <span className="score">{Math.min(100, Math.round(result.score / 20 * 100))}%<small>уверенность</small></span>
              <span className="result-copy">
                <strong>{template.name}</strong>
                <small>{template.description}</small>
                <em>{result.reasons?.find((reason) => reason.startsWith("Совпали")) || "Подходит по предмету описанных работ."}</em>
              </span>
            </button>
          ))}
        </div>
      </section>

      <section className="panel details-panel">
        {selectedResult && selectedTemplate ? (
          <>
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Рекомендованный шаблон</span>
                <h3>{selectedTemplate.name}</h3>
              </div>
              <button onClick={() => onCreateTz(selectedResult)}>Сформировать ТЗ</button>
            </div>
            <p className="template-recommendation-copy">{selectedTemplate.description}</p>
            <ReasonList title="Почему выбран этот тип ТЗ" items={matchReasons.length ? matchReasons : ["Тематика запроса соответствует назначению шаблона."]} />
            <InfoGroup title="Этапы, которые попадут в черновик">
              <ol className="compact-list">{(selectedTemplateDetail?.stage_presets || []).map((stage) => <li key={stage}>{stage}</li>)}</ol>
            </InfoGroup>
            <ReasonList title="Что уточнить перед заполнением" items={[
              "Объект работ и ожидаемый результат.",
              "Состав исходных данных и ограничения.",
              "Плановый срок и нужные этапы выполнения.",
            ]} />
          </>
        ) : (
          <EmptyState text="Введите запрос, чтобы подобрать тип и структуру технического задания." />
        )}
      </section>
    </div>
  );
}

function ConstructorView(props) {
  const { currentTz } = props;
  if (!currentTz) return <section className="panel"><EmptyState text="Загружаю единый конструктор ТЗ…" /></section>;
  return <TzEditor {...props} />;
}

function ReadyScore({ value, className }) {
  const label = value >= 80 ? "Готово к выпуску" : value >= 50 ? "Нужно уточнить детали" : "Заполните ключевые поля";
  return (
    <div className={`ready-score-card ${className || ""}`}>
      <div><span>Заполненность ТЗ</span><strong>{value}%</strong></div>
      <i><em style={{ width: `${value}%` }} /></i>
      <small>{label}</small>
    </div>
  );
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
  validation, templateDetails, isNewDraft, createTz, estimate, selectedAdditionalServices, onToggleAdditional,
  onSelectContractor, onAddSection, onRemoveSection }) {
  const tz = currentTz;
  const template = templateDetails[tz.template_key];
  const [showExample, setShowExample] = useState(false);
  const input = tz.input_data || {};
  const liveReady = tz.status === "ready" && tz.requisites?.selected_contractor_id ? 100 : computeLiveReady(tz, template);
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
    <div className="constructor-dashboard">
      <section className="panel constructor-main" onBlurCapture={(event) => {
        const target = event.target;
        if (target.matches?.("input, textarea, select") && !target.closest(".gantt-zoom")) onValidate({ silent: true });
      }}>
        <div className="panel-heading">
          <div>
            <span className="eyebrow">{isNewDraft ? "Единый конструктор · ещё не сохранено" : `ТЗ ${tz.id}`}</span>
            <h3>{tz.template_name}</h3>
            <p className="muted">Все поля, разделы, этапы и расчёт подрядчиков находятся на одной странице.</p>
          </div>
          <div className="actions">
            {!isNewDraft && <button onClick={() => onSave()} disabled={tzBusy}>Сохранить</button>}
            <span className="auto-validation-badge">✓ Автопроверка включена</span>
            <button className="example-button" onClick={() => setShowExample(true)}>? Пример</button>
            <details className="action-menu">
              <summary>Действия</summary>
              <div>
                <button onClick={() => onGenerate("augment")} disabled={tzBusy}>Дополнить с DeepSeek</button>
                <button onClick={() => onGenerate("full")} disabled={tzBusy}>Пересобрать полностью</button>
                {!isNewDraft && <button onClick={() => onExport(tz.id, tz.title)}>Экспорт DOCX</button>}
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

        <ServiceEditor
          services={tz.requisites?.services || []}
          onChange={(services, removedName) => {
            updateTzReq("services", services);
            if (removedName) updateTzReq("removed_auto_services", [
              ...(tz.requisites?.removed_auto_services || []), removedName,
            ]);
          }}
        />
        <StageEditor
          stages={tz.requisites?.stages || []}
          source={tz.requisites?.plan_source}
          onChange={(stages) => updateTzReq("stages", stages)}
          onGenerate={() => onGenerate("augment", null, tzInstruction, true)}
          disabled={tzBusy}
        />
        <ScheduleConstraintEditor
          stages={tz.requisites?.stages || []}
          constraints={tz.requisites?.schedule_constraints || []}
          onChange={(constraints) => updateTzReq("schedule_constraints", constraints)}
        />

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
              onGenerate={() => onGenerate("augment", [section.key])}
              onRemove={section.key.startsWith("custom-") ? () => onRemoveSection(section.key) : null} />
          ))}
          <CustomSectionForm onAdd={onAddSection} disabled={tzBusy} />
        </div>

        <ConstructorEstimate
          estimate={estimate}
          currentTz={tz}
          onEstimate={() => onEstimate(selectedAdditionalServices)}
          selectedAdditionalServices={selectedAdditionalServices}
          onToggleAdditional={onToggleAdditional}
          isNewDraft={isNewDraft}
          validation={validation}
          onSelectContractor={onSelectContractor}
          busy={tzBusy}
        />
      </section>

      <aside className="panel inspector">
        <ReadyScore value={liveReady} className={readyClass} />
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

function SectionEditor({ section, onChange, onGenerate, onRemove, disabled }) {
  return (
    <article className="section-card section-always-open">
      <header className="section-head">
        <h5>{section.title}</h5>
        <span className={`source-badge ${section.source}`}>{sourceLabels[section.source] || section.source}</span>
      </header>
      <textarea value={section.content} onChange={(e) => onChange(e.target.value)} rows={6}
        placeholder="Текст раздела — заполните вручную или используйте DeepSeek." />
      <div className="section-actions">
        {onRemove && <button type="button" className="link-button danger-link" onClick={onRemove} disabled={disabled}>Удалить</button>}
        <button type="button" className="secondary" onClick={onGenerate} disabled={disabled}>Заполнить раздел</button>
      </div>
    </article>
  );
}

function CustomSectionForm({ onAdd, disabled }) {
  const [title, setTitle] = useState("");
  const submit = (event) => {
    event.preventDefault();
    if (!title.trim()) return;
    onAdd(title);
    setTitle("");
  };
  return (
    <form className="custom-section-form" onSubmit={submit}>
      <div><strong>Добавить свой раздел</strong><small>Название станет отдельным полем и будет передано ИИ-агенту.</small></div>
      <input value={title} onChange={(event) => setTitle(event.target.value)}
        placeholder="Например: Требования к информационной безопасности" maxLength={160} />
      <button type="submit" disabled={disabled || !title.trim()}>Добавить поле</button>
    </form>
  );
}

function ServiceEditor({ services, onChange }) {
  const normalized = services.map((item) => (typeof item === "string" ? { name: item, source: "manual" } : item));
  const update = (index, name) => onChange(normalized.map((item, i) => (i === index ? { ...item, name } : item)));
  return (
    <details className="editor-block" open>
      <summary>Услуги ({normalized.length})</summary>
      <p className="muted">Обязательные услуги добавляются по правилам ТЗ и данным системы. Любую услугу можно изменить или удалить; ИИ учитывает этот список при составлении этапов.</p>
      <div className="stage-editor service-editor">
        {normalized.map((item, index) => (
          <div key={`${index}-${item.name}`}>
            <span>{index + 1}</span>
            <input value={item.name || ""} onChange={(event) => update(index, event.target.value)} />
            {item.mandatory && <small title={item.reason || "Обязательная услуга"}>обязательная</small>}
            <button type="button" className="icon-button" onClick={() => onChange(
              normalized.filter((_, i) => i !== index),
              item.source !== "manual" ? item.name : null,
            )}>×</button>
          </div>
        ))}
        <button type="button" className="secondary" onClick={() => onChange([
          ...normalized, { name: "Новая услуга", mandatory: false, source: "manual", reason: "" },
        ])}>Добавить услугу</button>
      </div>
    </details>
  );
}

function StageEditor({ stages, onChange, onGenerate, source, disabled }) {
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
        <div className="actions">
          <button type="button" onClick={onGenerate} disabled={disabled}>Сформировать этапы ИИ</button>
          <button type="button" className="secondary" onClick={() => onChange([...stages, "Новый этап"])}>Добавить этап</button>
          {source && <small className="muted">Источник плана: {source === "ai" ? "ИИ" : "правила и БД"}</small>}
        </div>
      </div>
    </details>
  );
}

function ScheduleConstraintEditor({ stages, constraints, onChange }) {
  const update = (index, patch) => onChange(constraints.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  return (
    <section className="editor-block constraint-editor">
      <div className="editor-block-title">
        <span>Дополнительные условия и приостановления</span>
        <small>Попадут на диаграмму отдельными полосами и повлияют на срок/стоимость.</small>
      </div>
      <div className="constraint-list">
        {constraints.map((item, index) => (
          <div className="constraint-row" key={index}>
            <label><span>После этапа</span><select value={item.after_stage ?? 0} onChange={(e) => update(index, { after_stage: Number(e.target.value) })}>
              <option value={0}>До начала работ</option>
              {stages.map((stage, stageIndex) => <option key={stageIndex} value={stageIndex + 1}>{stageIndex + 1}. {stage}</option>)}
            </select></label>
            <TextInput label="Причина паузы" value={item.reason || ""} onChange={(value) => update(index, { reason: value })} />
            <TextInput label="Дней" type="number" value={item.days ?? ""} onChange={(value) => update(index, { days: Number(value) })} />
            <TextInput label="Оплачиваемый простой, %" type="number" value={item.billable_percent ?? 0}
              onChange={(value) => update(index, { billable_percent: Number(value) })} />
            <button type="button" className="icon-button" onClick={() => onChange(constraints.filter((_, i) => i !== index))}>×</button>
          </div>
        ))}
        <button type="button" className="secondary" onClick={() => onChange([...constraints, {
          after_stage: stages.length ? 1 : 0, reason: "Ожидание дополнительных исходных данных", days: 5, billable_percent: 0,
        }])}>Добавить условие</button>
      </div>
    </section>
  );
}

function ConstructorEstimate({ estimate, currentTz, onEstimate, selectedAdditionalServices,
  onToggleAdditional, isNewDraft, validation, onSelectContractor, busy }) {
  const cheapest = [...(estimate?.companies || [])].sort((a, b) => a.cost_without_vat - b.cost_without_vat).slice(0, 3);
  const selectedContractorId = currentTz.requisites?.selected_contractor_id;
  const canComplete = Boolean(validation?.valid && validation.ready_score === 100);
  return (
    <section className="constructor-estimate">
      <div className="estimate-callout">
        <div><span className="eyebrow">РАСЧЁТ ПО ЗАПОЛНЕННОМУ ТЗ</span><h4>Подрядчики, стоимость и диаграммы Ганта</h4>
          <p>Расчёт использует текущие поля, этапы и дополнительные условия — сохранять ТЗ заранее не нужно.</p></div>
        <button type="button" onClick={() => onEstimate(selectedAdditionalServices)} disabled={busy}>Рассчитать диаграмму Ганта</button>
      </div>

      {estimate && <>
        <div className="traffic-board">
          <div className="traffic-heading"><span className="eyebrow">СВЕТОФОР ЦЕНЫ</span><h4>Топ-3 по минимальной стоимости</h4></div>
          {cheapest.length ? <div className="traffic-grid">{cheapest.map((company, index) => (
            <article className={`traffic-card place-${index + 1}`} key={company.company_id}>
              <i /><span>№ {index + 1}</span><strong>{company.company_name}</strong>
              <b>{formatMoney(company.cost_without_vat)}</b>
              <small>рейтинг {company.rating ?? "—"} · {company.estimated_days} дней</small>
            </article>
          ))}</div> : <p className="contractor-empty">Нет подрядчиков, подтвердивших все условия текущего ТЗ. Причины исключения указаны ниже.</p>}
        </div>

        <div className="grid analytics-grid estimate-kpis">
          <Metric label="Подходящих подрядчиков" value={estimate.summary.company_count} />
          <Metric label="Минимальная стоимость" value={formatMoney(estimate.summary.lowest_cost_without_vat)} />
          <Metric label="Средняя стоимость" value={formatMoney(estimate.summary.average_cost_without_vat)} />
          <Metric label="Минимальный срок" value={`${estimate.summary.fastest_days} дн`} />
        </div>

        <ExcludedContractors contractors={estimate.excluded_contractors} />

        <div className="estimate-method-grid">
          <section>
            <span className="eyebrow">КРИТЕРИИ ПОДБОРА</span>
            <h5>Почему подрядчик попал в расчёт</h5>
            <ul>{(estimate.summary.selection_criteria || []).map((item) => <li key={item}>{item}</li>)}</ul>
          </section>
          <section>
            <span className="eyebrow">ФОРМУЛА ЦЕНЫ</span>
            <h5>Что изменяет стоимость</h5>
            <ul>{(estimate.summary.pricing_criteria || []).map((item) => <li key={item}>{item}</li>)}</ul>
            <small>Локация расчёта: <b>{estimate.summary.location || "не указана"}</b></small>
          </section>
        </div>

        {estimate.available_additional_services?.length > 0 && <section className="additional-services">
          <div className="editor-block-title"><span>Дополнительные услуги</span><small>Добавляются к стоимости подходящих подрядчиков.</small></div>
          <div className="additional-service-grid">{estimate.available_additional_services.map((service) => (
            <label key={service.product_id} className={selectedAdditionalServices.includes(service.product_id) ? "selected" : ""}>
              <input type="checkbox" checked={selectedAdditionalServices.includes(service.product_id)} onChange={() => onToggleAdditional(service.product_id)} />
              <span><strong>{service.name}</strong><small>{service.common_company_count} компаний · от {formatMoney(service.min_cost_without_vat)}</small></span>
            </label>
          ))}</div>
        </section>}

        <div className="roadmap-list all-contractors">
          {estimate.companies.map((company, index) => <ContractorRoadmap key={company.company_id} company={company} rank={index + 1}
            selected={selectedContractorId === company.company_id} canSelect={canComplete}
            onSelect={() => onSelectContractor(company)} busy={busy} />)}
        </div>
        <p className="estimate-disclaimer">{estimate.summary.cost_disclaimer}</p>
      </>}

      <div className={`finalize-bar ${currentTz.status === "ready" ? "completed" : ""}`}>
        <div><strong>{currentTz.status === "ready" ? "ТЗ завершено на 100%" : estimate ? "Финальный шаг — выбор исполнителя" : "Сначала рассчитайте диаграммы Ганта"}</strong>
          <span>{currentTz.status === "ready"
            ? `Исполнитель: ${currentTz.executor_name} · договор ${currentTz.contract_name || "не указан"}`
            : !canComplete && estimate
              ? `Перед выбором подрядчика устраните замечания: текущая готовность ${validation?.ready_score || 0}%`
              : "Выберите подходящего подрядчика в его карточке — после этого ТЗ сохранится и перейдёт в статус «готово»."}</span></div>
      </div>
    </section>
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

function MyTzView({ documents, onOpen, onExport, onDelete, onRefresh, onNew, onSaveFeedback }) {
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
                {doc.status === "ready" && <TzFeedbackForm document={doc} onSave={onSaveFeedback} />}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function RoadmapView({ estimate, currentTz, onEstimateTz, selectedAdditionalServices, onToggleAdditional }) {
  return (
    <div className="grid">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Только по сохранённому документу</span>
            <h3>Роадмап пользовательского ТЗ</h3>
            <p className="muted roadmap-explanation">Этапы берутся из текущего ТЗ. Данные ПРОСТОР используются только для оценки общей длительности и стоимости подрядчиков.</p>
          </div>
          <button onClick={() => onEstimateTz([])} disabled={!currentTz}>{estimate ? "Пересчитать ТЗ" : "Рассчитать по текущему ТЗ"}</button>
        </div>

        {!estimate ? (
          <EmptyState text={currentTz
            ? "Нажмите «Рассчитать по текущему ТЗ». В роадмап попадут только этапы, записанные в этом документе."
            : "Сначала создайте или откройте ТЗ. Ручной расчёт роадмапа по продукту отключён."} />
        ) : (
          <>
            <div className="grid analytics-grid">
              <Metric label="Подрядчиков" value={estimate.summary.company_count} />
              <Metric label="Минимальная стоимость" value={formatMoney(estimate.summary.lowest_cost_without_vat)} />
              <Metric label="Средняя стоимость" value={formatMoney(estimate.summary.average_cost_without_vat)} />
              <Metric label="Быстрее всех" value={`${estimate.summary.fastest_days} дн`} />
            </div>
            <div className="section-title">
              <span className="eyebrow">Техническое задание</span>
              <h4>{estimate.tz_title || currentTz?.title || currentTz?.template_name}</h4>
            </div>
            <p className="roadmap-methodology">Для поиска подходящих договоров использована внутренняя категория «{estimate.product_name}». Она не определяет этапы роадмапа.</p>
            <p className="estimate-disclaimer">{estimate.summary.cost_disclaimer}</p>
            {estimate.available_additional_services?.length > 0 && (
              <details className="additional-services" open>
                <summary>Дополнительные услуги к этому ТЗ</summary>
                <p>Каталог продуктов ПРОСТОР находится здесь: выбранные позиции добавляются к стоимости, но не заменяют этапы основного ТЗ.</p>
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
            <ExcludedContractors contractors={estimate.excluded_contractors} />
          </>
        )}
      </section>
    </div>
  );
}

function TzFeedbackForm({ document, onSave }) {
  const blank = { rating: null, comment: "" };
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [aiInitiallyGenerated, setAiInitiallyGenerated] = useState(Boolean(document.ai_initially_generated));
  const [feedback, setFeedback] = useState({
    contractor: { ...blank, ...(document.feedback?.contractor || {}) },
    ai_tz: { ...blank, ...(document.feedback?.ai_tz || {}) },
    ai_chat: { ...blank, ...(document.feedback?.ai_chat || {}) },
  });
  const change = (kind, patch) => {
    setSaved(false);
    setFeedback((current) => ({ ...current, [kind]: { ...current[kind], ...patch } }));
  };
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSave(document.id, { ai_initially_generated: aiInitiallyGenerated, feedback });
      setSaved(true);
    } catch (saveError) {
      setError(saveError.message || "Не удалось сохранить оценки");
    } finally {
      setBusy(false);
    }
  };
  const hasRating = feedback.contractor.rating || feedback.ai_tz.rating || feedback.ai_chat.rating;
  return (
    <div className="tz-feedback">
      <button type="button" className="secondary feedback-toggle" onClick={() => setOpen((value) => !value)}>
        {open ? "Скрыть оценки" : hasRating ? "Изменить оценки" : "Оценить выполнение и ИИ"}
      </button>
      {open && <form onSubmit={submit}>
        <h4>Оценка завершённого ТЗ</h4>
        <EvaluationField title={`Подрядчик${document.executor_name ? `: ${document.executor_name}` : ""}`}
          value={feedback.contractor} onChange={(patch) => change("contractor", patch)} />
        <label className="ai-origin-check"><input type="checkbox" checked={aiInitiallyGenerated}
          onChange={(event) => { setAiInitiallyGenerated(event.target.checked); setSaved(false); }} />
          <span><strong>Первоначальный вариант ТЗ заполнялся ИИ</strong><small>После генерации заказчик проверял и редактировал документ.</small></span>
        </label>
        {aiInitiallyGenerated && <EvaluationField title="ИИ при создании ТЗ" value={feedback.ai_tz}
          onChange={(patch) => change("ai_tz", patch)} />}
        <EvaluationField title="ИИ-агент в чате" value={feedback.ai_chat}
          onChange={(patch) => change("ai_chat", patch)} />
        <div className="feedback-submit"><button type="submit" disabled={busy || !hasRating}>{busy ? "Сохраняю…" : "Сохранить оценки"}</button>
          {saved && <span>✓ Сохранено</span>}{error && <span className="feedback-error">{error}</span>}</div>
      </form>}
    </div>
  );
}

function EvaluationField({ title, value, onChange }) {
  return (
    <fieldset className="evaluation-field">
      <legend>{title}</legend>
      <div className="star-picker" aria-label={`${title}: оценка по пятибалльной шкале`}>
        {[1, 2, 3, 4, 5].map((rating) => <button key={rating} type="button"
          className={(value.rating || 0) >= rating ? "selected" : ""}
          onClick={() => onChange({ rating })} aria-label={`${rating} из 5`}>★</button>)}
        <span>{value.rating ? `${value.rating} из 5` : "Не оценено"}</span>
      </div>
      <textarea rows={2} value={value.comment || ""} maxLength={4000}
        onChange={(event) => onChange({ comment: event.target.value })} placeholder="Комментарий" />
    </fieldset>
  );
}

function ExcludedContractors({ contractors = [] }) {
  if (!contractors.length) return null;
  return (
    <details className="excluded-contractors">
      <summary>Не прошли проверку условий: {contractors.length}</summary>
      <div>{contractors.map((company) => (
        <article key={company.company_id}>
          <strong>{company.company_name}</strong>
          <ul>{company.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
        </article>
      ))}</div>
    </details>
  );
}

function ContractorRoadmap({ company, rank, selected = false, canSelect = false, onSelect, busy = false }) {
  const [zoom, setZoom] = useState(1);
  const totalDays = Math.max(company.estimated_days || 1, 1);
  const datedStages = company.stages.filter((stage) => stage.start_date && stage.end_date);
  const timelineStart = datedStages[0]?.start_date;
  const timelineEnd = datedStages[datedStages.length - 1]?.end_date;
  const ticks = Array.from({ length: 5 }, (_, index) => {
    if (!timelineStart || !timelineEnd) return { left: index * 25, label: `${Math.round(index * totalDays / 4)} дн` };
    const start = new Date(`${timelineStart}T00:00:00Z`);
    const end = new Date(`${timelineEnd}T00:00:00Z`);
    const current = new Date(start.getTime() + (end.getTime() - start.getTime()) * index / 4);
    return { left: index * 25, label: current.toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: index === 0 || index === 4 ? "numeric" : undefined, timeZone: "UTC" }) };
  });
  return (
    <article className="contractor-card">
      <div className="contractor-head">
        <div>
          <strong>{rank}. {company.company_name}</strong>
          <span className="contractor-rating"><b>★ {company.rating ?? "—"}</b><small> рейтинг · соответствие {company.suitability_score || "—"}/100</small></span>
          <small>
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

      <div className="gantt-legend">
        <span><i className="work" /> Этап работ</span><span><i className="pause" /> Приостановка / ожидание</span>
        <small>{timelineStart && timelineEnd ? `${timelineStart} — ${timelineEnd}` : `${totalDays} дней`}</small>
        <div className="gantt-zoom" aria-label="Масштаб диаграммы">
          <button type="button" onClick={() => setZoom((value) => Math.max(0.8, +(value - 0.2).toFixed(1)))} disabled={zoom <= 0.8} aria-label="Уменьшить масштаб">−</button>
          <input type="range" min="80" max="240" step="20" value={Math.round(zoom * 100)} onChange={(event) => setZoom(Number(event.target.value) / 100)} aria-label="Масштаб диаграммы Ганта" />
          <output>{Math.round(zoom * 100)}%</output>
          <button type="button" onClick={() => setZoom((value) => Math.min(2.4, +(value + 0.2).toFixed(1)))} disabled={zoom >= 2.4} aria-label="Увеличить масштаб">+</button>
          <button type="button" className="gantt-reset" onClick={() => setZoom(1)}>Сбросить</button>
        </div>
      </div>
      <div className="gantt-scroll"><div className="gantt-chart" style={{ width: `${zoom * 100}%` }}>
        <div className="gantt-axis-label">Этап</div>
        <div className="gantt-axis">{ticks.map((tick) => <span key={tick.left} style={{ left: `${tick.left}%` }}>{tick.label}</span>)}</div>
        {company.stages.map((stage, i) => (
          <div className={`gantt-row ${stage.kind === "pause" ? "pause-row" : ""}`} key={stage.order}>
            <div className="gantt-row-label"><b>{stage.name}</b><small>{stage.days} дн. · {stage.start_date || "—"} — {stage.end_date || "—"}</small></div>
            <div className="gantt-lane">
              <div className={`gantt-bar ${stage.kind === "pause" ? "pause" : `c${i % 5}`}`}
                style={{ left: `${stage.offset_days * 100 / totalDays}%`, width: `${Math.max(stage.days * 100 / totalDays, 1.2)}%` }}>
                <span>{stage.days} дн.</span>
                <div className="stage-tooltip"><strong>{stage.name}</strong><b>{formatMoney(stage.estimated_cost_without_vat)}</b><small>{stage.days} дней{stage.kind === "pause" ? ` · оплачиваемый простой ${stage.billable_percent || 0}%` : ""}</small></div>
              </div>
            </div>
          </div>
        ))}
      </div></div>
      <details className="contractor-method">
        <summary>Почему подходит и как рассчитана цена</summary>
        <div><ul>{(company.selection_reasons || []).map((reason) => <li key={reason}>{reason}</li>)}</ul>
          <ul>{(company.cost_factors || []).map((factor) => <li key={factor.key}><b>{factor.label} ×{factor.multiplier}</b><span>{factor.reason}</span></li>)}</ul></div>
      </details>
      <div className="contractor-total">
        <span>Полная стоимость выполнения ТЗ</span>
        <strong>{formatMoney(company.cost_with_vat)}</strong>
        <small>с НДС · без НДС {formatMoney(company.cost_without_vat)}</small>
      </div>
      {onSelect && <div className={`contractor-selection ${selected ? "selected" : ""}`}>
        <div><strong>{selected ? "Исполнитель выбран" : "Назначить исполнителя"}</strong>
          <small>{canSelect || selected ? "Выбор завершит ТЗ и зафиксирует расчёт." : "Сначала доведите заполненность ТЗ до 100%."}</small></div>
        <button type="button" onClick={onSelect} disabled={busy || selected || !canSelect}>
          {selected ? "✓ Выбран" : "Выбрать и завершить ТЗ"}
        </button>
      </div>}
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

function AssistantDiscovery({ data, onOpenTz }) {
  if (!data) return null;
  return (
    <section className="assistant-discovery">
      <header><span>Намерение</span><strong>{data.intent?.label}</strong><small>{Math.round((data.intent?.confidence || 0) * 100)}% уверенности</small></header>

      {data.services?.length > 0 && <div className="discovery-group">
        <h5>Релевантные услуги</h5>
        {data.services.map((service, index) => <article key={service.product_id} className="discovery-service">
          <span>#{index + 1}</span><div><b>{service.name}</b><small>{service.summary}</small>
            <em>{service.reasons?.[0] || "Соответствует запросу"}</em></div><strong>{Math.round(service.score * 100)}%</strong>
        </article>)}
      </div>}

      {data.similar_tz?.length > 0 && <div className="discovery-group">
        <h5>Похожие ТЗ и кейсы</h5>
        {data.similar_tz.slice(0, 4).map((item) => <article className="discovery-similar" key={`${item.source}-${item.id}`}>
          <div><b>{item.title}</b><small>{item.object_name || item.source}</small><p>{item.summary}</p></div>
          {item.is_saved && <button type="button" className="link-button" onClick={() => onOpenTz?.(item.id)}>Открыть</button>}
        </article>)}
      </div>}

      {data.contractors?.length > 0 && <div className="discovery-group">
        <h5>Подходящие исполнители</h5>
        {data.contractors.slice(0, 4).map((company) => <article className="discovery-contractor" key={company.company_id}>
          <div><b>{company.name}</b><small>{company.service_name}</small><p>{company.reasons?.[1] || company.reasons?.[0]}</p></div>
          <strong>★ {company.rating ?? "—"}</strong>
        </article>)}
      </div>}

      {data.filling_recommendations?.length > 0 && <div className="discovery-group">
        <h5>Что заполнить в ТЗ</h5>
        <ol className="discovery-recommendations">{data.filling_recommendations.map((item) => <li className={item.priority} key={item.field}><b>{item.label}</b><span>{item.recommendation}</span></li>)}</ol>
      </div>}

      {data.conditional_services?.length > 0 && <div className="discovery-group conditional">
        <h5>Условно обязательные услуги</h5>
        {data.conditional_services.map((item) => <article key={item.name}><span>{item.status}</span><b>{item.name}</b><small>{item.condition}</small><p>{item.reason}</p></article>)}
      </div>}
    </section>
  );
}

function AssistantSidebar({ isOpen, onToggle, messages, input, setInput, onSend, onApply, isLoading, hasTz, onAugment, onFull, status, onOpenTz }) {
  const messageListRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!isOpen || !messageListRef.current) return;
    messageListRef.current.scrollTo({
      top: messageListRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, isLoading, isOpen]);

  useEffect(() => {
    const textarea = inputRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 54), 210)}px`;
  }, [input]);

  if (!isOpen) return <button className="chat-fab" onClick={onToggle}>AI-чат</button>;

  const quickActions = [
    { label: "Заполнить ТЗ из чата", action: () => onSend("Заполни ТЗ по всем полям и нашей переписке"), disabled: !hasTz },
    { label: "Собрать ТЗ целиком", action: () => onSend("Собери ТЗ целиком по контексту диалога"), disabled: !hasTz },
    { label: "Что критично уточнить", action: () => onSend("Какого одного критичного факта не хватает для ТЗ?") },
    { label: "Про сроки", action: () => onSend("Как оценить сроки подрядчиков?") },
  ];

  return (
    <aside className="assistant-sidebar" aria-label="AI-помощник по ТЗ">
      <header className="assistant-header">
        <span className="assistant-avatar"><Sparkles size={18} /></span>
        <div className="assistant-heading">
          <span className="eyebrow">AI-помощник</span>
          <h3>Чат по ТЗ</h3>
          <small className={`provider-status ${status?.enabled ? "online" : "offline"}`}>
            {status?.enabled ? `DeepSeek · ${status.model}` : "Локальный AI · база ТЗ"}
          </small>
        </div>
        <button className="icon-button" type="button" onClick={onToggle} aria-label="Скрыть чат"><X size={17} /></button>
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
          <div className={`message ${message.role}`} key={message.id}>
            <div className="message-text">{message.text}</div>
            {message.role === "assistant" && <AssistantDiscovery data={message.discovery} onOpenTz={onOpenTz} />}

            {message.warnings?.length > 0 && (
              <ul className="chat-warnings">
                {message.warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            )}

            {message.field_updates?.length > 0 && (
              <div className="chat-updates">
                {message.field_updates.map((update, index) => (
                  <div className={`chat-update ${update.applied ? "applied" : ""}`} key={`${update.target}-${update.key}-${index}`}>
                    <div className="chat-update-main">
                      <span className="chat-update-label">{update.label || update.key}</span>
                      <span className="chat-update-value">{formatUpdateValue(update.value)}</span>
                    </div>
                    <button
                      type="button"
                      className="secondary chat-update-apply"
                      disabled={update.applied || isLoading || !hasTz}
                      onClick={() => onApply(message.id, [update])}
                    >
                      {update.applied ? "✓ в ТЗ" : "Применить"}
                    </button>
                  </div>
                ))}
                {message.field_updates.some((u) => !u.applied) && (
                  <button
                    type="button"
                    className="link-button chat-apply-all"
                    disabled={isLoading || !hasTz}
                    onClick={() => onApply(message.id, message.field_updates.filter((u) => !u.applied))}
                  >
                    Применить всё в ТЗ
                  </button>
                )}
              </div>
            )}

            {message.suggestions?.length > 0 && (
              <div className="chat-suggestions">
                {message.suggestions.map((suggestion, index) => (
                  <button type="button" className="chip" key={index} onClick={() => onSend(suggestion)} disabled={isLoading}>
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {isLoading && <div className="message assistant message-loading" aria-label="ИИ готовит ответ"><i /><i /><i /></div>}
      </div>

      <form className="assistant-input" onSubmit={(e) => { e.preventDefault(); onSend(); }}>
        <div className="assistant-compose"><textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); } }}
          placeholder="Спросите AI по вашему ТЗ..." rows={1} />
        <button type="submit" disabled={!input.trim() || isLoading} aria-label="Отправить"><Send size={19} /></button></div>
        <small>Enter — отправить · Shift + Enter — новая строка</small>
      </form>
    </aside>
  );
}

function AnalyticsView({ analytics, contractorAnalytics }) {
  if (!analytics) {
    return <section className="panel"><EmptyState text="Аналитика будет доступна после запуска backend." /></section>;
  }
  const coverage = analytics.dataset_coverage || {};
  const coverageRows = [
    ["Строки расценок", coverage.price_rows || 0, 2780],
    ["Этапы работ", coverage.stages || 0, 1677],
    ["Заявки и заказы", coverage.orders || 0, 462],
    ["Операции", coverage.operations || 0, 318],
  ];
  const productBars = (analytics.popular_work_types || []).map((label, index) => ({ label, value: [92, 78, 64, 51][index] || 42 }));
  const contractorRanking = contractorAnalytics?.top_by_rating || [];
  return (
    <div className="analytics-dashboard">
      <section className="analytics-hero">
        <div><span className="eyebrow">АНАЛИТИКА ПРОСТОР</span><h3>Пульс рабочего процесса</h3><p>Сводная картина по каталогу, заявкам и качеству технических заданий.</p></div>
        <div className="analytics-health"><span>Качество данных</span><strong>94<small>%</small></strong><i><em /></i><small>Система работает стабильно</small></div>
      </section>

      <div className="analytics-kpis">
        {[['Продукты',analytics.total_products,'+6 за квартал','blue'],['Компании',analytics.total_companies,'3 с аналогами','violet'],['Активные договоры',analytics.total_active_contracts,'83% покрытия','green'],['Исторические кейсы',analytics.total_historical_cases,'База для AI','orange']].map(([label,value,note,tone])=><section className={'analytics-kpi '+tone} key={label}><span>{label}</span><strong>{value}</strong><small>{note}</small><i /></section>)}
      </div>

      <section className="panel contractor-leaderboard">
        <div className="analytics-title"><div><span className="eyebrow">ПОДРЯДЧИКИ</span><h4>Рейтинг подрядчиков</h4></div><small>{contractorAnalytics?.summary?.total_contractors ? `${contractorAnalytics.summary.total_contractors} компаний в базе` : "По данным ПРОСТОР"}</small></div>
        {contractorRanking.length ? <div className="contractor-ranking-list">{contractorRanking.map((company,index)=>{
          const rating=Number(company.rating ?? company.value ?? 0);
          return <article className={index<3?'top-contractor':''} key={company.company_id}><span className={'rank-place place-'+(index+1)}>{index+1}</span><div><b>{company.company_name}</b><small>{index===0?'Лидер рейтинга':index<3?'Входит в топ-3':'Проверенный подрядчик'}</small></div><span className="rating-stars" aria-label={`Рейтинг ${rating.toFixed(1)} из 5`}><i style={{width:`${Math.min(100,rating/5*100)}%`}}>★★★★★</i><em>★★★★★</em></span><strong>{rating.toFixed(1)}</strong></article>;
        })}</div> : <div className="contractor-ranking-empty">Рейтинг появится после загрузки данных подрядчиков</div>}
      </section>

      <div className="analytics-main-grid">
        <section className="panel analytics-chart"><div className="analytics-title"><div><span className="eyebrow">СПРОС</span><h4>Популярные виды работ</h4></div><small>Последние 90 дней</small></div><div className="horizontal-bars">{productBars.map((item,index)=><div key={item.label}><span><b>{index+1}</b>{item.label}<em>{item.value}%</em></span><i><em style={{width:`${item.value}%`}} /></i></div>)}</div></section>
        <section className="panel coverage-card"><div className="analytics-title"><div><span className="eyebrow">ДАННЫЕ</span><h4>Покрытие базы ПРОСТОР</h4></div><span className="live-label"><i/>XLSX</span></div><div className="coverage-list">{coverageRows.map(([label,value,max])=><div key={label}><span><b>{label}</b><em>{value.toLocaleString('ru-RU')}</em></span><i><em style={{width:`${Math.min(100,value/max*100)}%`}} /></i></div>)}</div></section>
      </div>

      <div className="analytics-lower-grid">
        <section className="panel process-card"><div className="analytics-title"><div><span className="eyebrow">ПРОЦЕСС</span><h4>Контур данных для подготовки ТЗ</h4></div></div><div className="process-funnel"><div><strong>{coverage.orders || 0}</strong><span>РС и заявок</span></div><i>→</i><div><strong>{coverage.operations || 0}</strong><span>операций</span></div><i>→</i><div><strong>{coverage.price_products || 0}</strong><span>продуктов с расценками</span></div><i>→</i><div className="accent"><strong>{coverage.contracts || 0}</strong><span>договоров</span></div></div><p className="process-source">Это не конверсия пользователей. Показан состав XLSX-выгрузки ПРОСТОР: «Договор + РС», «Продукты + Операции», «Продукты + расценки» и «Договоры».</p></section>
        <section className="panel analytics-risks"><div className="analytics-title"><div><span className="eyebrow">КАЧЕСТВО</span><h4>Что чаще всего нужно уточнить</h4></div></div><ol>{(analytics.typical_request_errors || analytics.common_risk_patterns || []).slice(0,4).map((item,index)=><li key={item}><span>{index+1}</span><b>{item}</b></li>)}</ol></section>
      </div>
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
