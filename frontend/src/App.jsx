import { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft, ArrowRight, Bot, BriefcaseBusiness, CalendarDays, Check,
  CheckCircle2, ChevronDown, CircleUserRound, Clock3, Copy, FileCheck2,
  FileText, History, LayoutDashboard, Menu, MessageCircleQuestion,
  Plus, Search, Send, Sparkles, X
} from './icons';

const requestsSeed = [
  { id: 'ЗА-2026-00421', title: 'Сопровождение инженерных работ', company: 'ООО «Газпромнефть-Заполярье»', date: '14 августа 2026', status: 'На согласовании', tone: 'warning' },
  { id: 'ЗА-2026-00398', title: 'Интегрированный концепт развития', company: 'АО «Газпромнефть-Ноябрьскнефтегаз»', date: '8 августа 2026', status: 'Сформирована', tone: 'success' },
  { id: 'ЗА-2026-00377', title: 'Концепт обустройства месторождения', company: 'ООО «Газпромнефть-Развитие»', date: '29 июля 2026', status: 'Черновик', tone: 'neutral' },
  { id: 'ЗА-2026-00341', title: 'Разработка проектно-технической документации', company: 'ПАО «Газпром нефть»', date: '17 июля 2026', status: 'Сформирована', tone: 'success' },
];

const assistantAnswers = {
  default: 'Я помогу подобрать шаблон, сформулировать требования или проверить заявку перед отправкой. Опишите задачу своими словами.',
  template: 'Для сопровождения инженерных работ рекомендую шаблон «Сопровождение инженерных работ и высокорисковых операций». Я могу открыть форму уже с ним.',
  status: 'Заявка ЗА-2026-00421 сейчас находится на согласовании. Следующий этап — проверка ответственным подразделением.',
  fields: 'Для создания заявки понадобятся заказчик, вид работ, желаемый срок, краткое описание и технические требования. Документы можно приложить в форме.'
};

function Logo() {
  return <div className="brand" onClick={() => location.reload()}><div className="brand-mark"><span>Г</span></div><div><strong>ПРОСТОР</strong><small>единое окно заказчика</small></div></div>;
}

function Header({ page, navigate }) {
  return <header><Logo /><nav>
    <button className={page === 'home' ? 'active' : ''} onClick={() => navigate('home')}><LayoutDashboard size={18}/>Главная</button>
    <button className={page === 'history' ? 'active' : ''} onClick={() => navigate('history')}><History size={18}/>Мои заявки</button>
  </nav><div className="header-actions"><button className="help"><MessageCircleQuestion size={20}/></button><div className="user"><span className="avatar">АА</span><span><b>Александра А.</b><small>Заказчик</small></span><ChevronDown size={16}/></div><button className="mobile-menu"><Menu/></button></div></header>;
}

function Assistant({ compact = false }) {
  const [messages, setMessages] = useState([{ from: 'bot', text: 'Здравствуйте! Я AI-помощник ПРОСТОР. Чем могу помочь?' }]);
  const [value, setValue] = useState('');
  const send = (preset) => {
    const text = (preset || value).trim(); if (!text) return;
    setMessages(m => [...m, { from: 'user', text }, { from: 'bot', text: assistantAnswers[text] || assistantAnswers.default }]); setValue('');
  };
  return <aside className={'assistant ' + (compact ? 'compact' : '')}>
    <div className="assistant-head"><div className="bot-icon"><Sparkles size={20}/></div><div><b>AI-помощник</b><small><i/>всегда на связи</small></div><button><X size={18}/></button></div>
    <div className="messages">{messages.map((m,i) => <div className={'message '+m.from} key={i}>{m.from==='bot' && <Bot size={18}/>}<span>{m.text}</span></div>)}</div>
    {messages.length < 3 && <div className="suggestions">
      <button onClick={() => send('template')}>Какой шаблон выбрать?</button><button onClick={() => send('fields')}>Что нужно для заявки?</button><button onClick={() => send('status')}>Статус последней заявки</button>
    </div>}
    <div className="chat-input"><input value={value} onChange={e=>setValue(e.target.value)} onKeyDown={e=>e.key==='Enter'&&send()} placeholder="Задайте вопрос..."/><button onClick={()=>send()}><Send size={18}/></button></div>
    <small className="ai-note">Ответы AI могут содержать неточности</small>
  </aside>;
}

function Home({ navigate, onRepeat, onOpen }) {
  return <div className="page-shell"><main className="main-content">
    <section className="welcome"><div><span className="eyebrow">ДОБРО ПОЖАЛОВАТЬ</span><h1>Добрый день, Александра!</h1><p>Создавайте заявки и следите за ходом их исполнения в одном месте.</p></div><div className="date"><CalendarDays size={18}/>17 августа, понедельник</div></section>
    <section className="hero-card"><div className="hero-copy"><div className="hero-icon"><FileText/></div><div><div className="ai-label"><Sparkles size={13}/>AI проверит заявку перед отправкой</div><h2>Новая заявка</h2><p>Опишите задачу, выберите подходящий шаблон и получите готовый комплект документов.</p><button className="primary" onClick={()=>navigate('create')}><Plus size={19}/>Создать заявку<ArrowRight size={18}/></button></div></div><div className="hero-art"><span/><span/><span/><FileCheck2/></div></section>
    <section className="section-head"><div><h2>Последние заявки</h2><p>Недавние документы и их текущий статус</p></div><button className="link" onClick={()=>navigate('history')}>Вся история <ArrowRight size={17}/></button></section>
    <div className="request-list">{requestsSeed.slice(0,3).map(r=><RequestRow key={r.id} item={r} onRepeat={onRepeat} onOpen={onOpen}/>)}</div>
    <div className="stats"><div><span className="stat-icon blue"><FileText/></span><p><b>12</b>Всего заявок</p></div><div><span className="stat-icon green"><CheckCircle2/></span><p><b>8</b>Сформировано</p></div><div><span className="stat-icon orange"><Clock3/></span><p><b>3</b>В работе</p></div></div>
  </main><Assistant /></div>;
}

function RequestRow({item,onRepeat,onOpen}) { return <article className="request-row"><div className="doc-icon"><FileText size={21}/></div><div className="request-info request-clickable" onClick={()=>onOpen(item)}><div><b>{item.title}</b><span className={'badge '+item.tone}>{item.status}</span></div><p>{item.id}<i/> {item.company}<i/> {item.date}</p></div><button className="repeat" onClick={()=>onRepeat(item)}><Copy size={16}/>Повторить</button><button className="round" onClick={()=>onOpen(item)} aria-label="Открыть заявку"><ArrowRight size={18}/></button></article> }

function HistoryPage({navigate,onRepeat,onOpen}) { const [query,setQuery]=useState(''); const [statusFilter,setStatusFilter]=useState('Все статусы'); const filtered=useMemo(()=>requestsSeed.filter(r=>(r.title+r.id+r.company).toLowerCase().includes(query.toLowerCase())&&(statusFilter==='Все статусы'||r.status===statusFilter)),[query,statusFilter]); return <div className="page-shell"><main className="wide-page embedded-page">
  <button className="back" onClick={()=>navigate('home')}><ArrowLeft size={17}/>На главную</button><div className="title-row"><div><h1>История заявок</h1><p>Все созданные заявки и комплекты документов</p></div><button className="primary" onClick={()=>navigate('create')}><Plus size={18}/>Создать заявку</button></div>
  <div className="filterbar"><div className="search"><Search size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Поиск по номеру, названию или компании"/></div><div className="filter-select"><select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}><option>Все статусы</option><option>На согласовании</option><option>Сформирована</option><option>Черновик</option></select><ChevronDown size={16}/></div><div className="period-chip"><CalendarDays size={15}/>2026 год</div></div>
  <div className="history-card"><div className="table-head"><span>Заявка</span><span>Дата создания</span><span>Статус</span><span/></div>{filtered.map(r=><div className="table-row" key={r.id}><div className="request-clickable" onClick={()=>onOpen(r)}><div className="doc-icon"><FileText size={20}/></div><span><b>{r.title}</b><small>{r.id} · {r.company}</small></span></div><span>{r.date}</span><span><em className={'badge '+r.tone}>{r.status}</em></span><span><button className="repeat" onClick={()=>onRepeat(r)}><Copy size={16}/>Повторить</button><button className="round" onClick={()=>onOpen(r)}><ArrowRight size={18}/></button></span></div>)}{!filtered.length&&<div className="empty-history"><Search size={28}/><b>Заявки не найдены</b><span>Измените запрос или выберите другой статус</span><button className="link" onClick={()=>{setQuery('');setStatusFilter('Все статусы')}}>Сбросить фильтры</button></div>}</div>
  <p className="count">Показано {filtered.length} из {requestsSeed.length} заявок</p>
  </main><Assistant /></div> }

const emptyForm = { title:'', company:'', category:'', deadline:'', description:'', template:'' };
function CreatePage({navigate,initial,notify}) { const [form,setForm]=useState(()=>initial ? {title:initial.title,company:initial.company,category:'Инженерные работы',deadline:'',description:'Требуется сформировать комплект документов для выполнения работ.',template:'Сопровождение инженерных работ'} : JSON.parse(localStorage.getItem('prostor-draft')||'null')||emptyForm); const [step,setStep]=useState(1); const [done,setDone]=useState(false); const [errors,setErrors]=useState({}); const set=(k,v)=>{setForm(f=>({...f,[k]:v}));setErrors(e=>({...e,[k]:false}))};
  useEffect(()=>{const timer=setTimeout(()=>{localStorage.setItem('prostor-draft',JSON.stringify(form));if(Object.values(form).some(Boolean))notify('Черновик автоматически сохранён','success')},600);return()=>clearTimeout(timer)},[form]);
  const proceed=()=>{const required=step===1?['title','company','category']:step===2?['template']:[];const missing=Object.fromEntries(required.filter(k=>!form[k].trim()).map(k=>[k,true]));if(Object.keys(missing).length){setErrors(missing);notify('Заполните обязательные поля','error');return}if(step===3){localStorage.removeItem('prostor-draft');setDone(true);notify('Заявка успешно создана','success')}else setStep(s=>s+1)};
  const completion=Math.round(Object.values(form).filter(Boolean).length/Object.keys(form).length*100);
  if(done) return <main className="success-screen"><div className="success-check"><Check size={38}/></div><h1>Заявка создана</h1><p>Черновик сохранён. Вы сможете вернуться к нему и дополнить данные в любое время.</p><strong>ЗА-2026-00432</strong><button className="primary" onClick={()=>navigate('history')}>Перейти к заявкам<ArrowRight size={18}/></button><button className="link" onClick={()=>navigate('home')}>На главную</button></main>;
  return <main className="form-page"><button className="back" onClick={()=>navigate(initial?'history':'home')}><ArrowLeft size={17}/>Назад</button><div className="form-heading"><div><span className="eyebrow">НОВАЯ ЗАЯВКА</span><h1>{initial?'Повтор заявки':'Создание заявки'}</h1><p>{initial?'Данные скопированы — проверьте и скорректируйте их.':'Заполните основные сведения — помощник подскажет на каждом этапе.'}</p></div><div className="completion"><span><b>{completion}%</b> заполнено</span><i><em style={{width:`${completion}%`}}/></i><small>Черновик сохраняется автоматически</small></div></div>
  <div className="stepper">{['Основная информация','Требования и документы','Проверка'].map((s,i)=><div className={step>=i+1?'current':''} key={s}><i>{step>i+1?<Check size={14}/>:i+1}</i><span>{s}<small>{i===0?'О заявке':i===1?'Детали':'Подтверждение'}</small></span></div>)}</div>
  <div className="form-layout"><section className="form-card">
  {step===1 && <><h2>Основная информация</h2><p className="muted">Укажите, что требуется выполнить и для какой компании.</p><label>Название заявки <b>*</b><input className={errors.title?'invalid':''} value={form.title} onChange={e=>set('title',e.target.value)} placeholder="Например, разработка концепта обустройства"/>{errors.title&&<small className="field-error">Укажите название заявки</small>}</label><div className="field-grid"><label>Компания-заказчик <b>*</b><select className={errors.company?'invalid':''} value={form.company} onChange={e=>set('company',e.target.value)}><option value="">Выберите компанию</option><option>ПАО «Газпром нефть»</option><option>ООО «Газпромнефть-Заполярье»</option><option>АО «Газпромнефть-Ноябрьскнефтегаз»</option><option>ООО «Газпромнефть-Развитие»</option></select>{errors.company&&<small className="field-error">Выберите компанию</small>}</label><label>Вид работ <b>*</b><select className={errors.category?'invalid':''} value={form.category} onChange={e=>set('category',e.target.value)}><option value="">Выберите вид работ</option><option>Инженерные работы</option><option>Проектирование</option><option>Геология</option><option>Разработка концепции</option></select>{errors.category&&<small className="field-error">Выберите вид работ</small>}</label></div><label>Краткое описание<textarea value={form.description} onChange={e=>set('description',e.target.value)} placeholder="Опишите задачу и ожидаемый результат"/></label></>}
  {step===2 && <><h2>Требования</h2><p className="muted">Выберите шаблон технического задания и укажите желаемый срок выполнения.</p><label>Шаблон технического задания <b>*</b><select className={errors.template?'invalid':''} value={form.template} onChange={e=>set('template',e.target.value)}><option value="">Выберите подходящий шаблон</option><option>Сопровождение инженерных работ</option><option>Интегрированный концепт развития</option><option>Концепт обустройства</option><option>Проектно-техническая документация</option></select>{errors.template&&<small className="field-error">Выберите шаблон</small>}</label><label>Желаемый срок выполнения<input type="date" value={form.deadline} onChange={e=>set('deadline',e.target.value)}/></label></>}
  {step===3 && <><div className="review-title"><div><h2>Проверьте данные</h2><p className="muted">AI проанализировал заявку перед созданием.</p></div><span className="ai-reviewed"><Sparkles size={14}/>Проверено AI</span></div><div className="ai-audit"><div className="score-ring" style={{'--score':form.description?92:84}}><strong>{form.description?'92':'84'}<small>%</small></strong><span>готовность</span></div><div className="audit-results"><h3>Заявка готова к отправке</h3><p><Check size={15}/>Обязательные данные заполнены</p><p><Check size={15}/>Шаблон соответствует виду работ</p><p className="audit-tip"><Sparkles size={15}/>{form.description?'Описание задачи сформулировано достаточно подробно':'Добавьте описание ожидаемого результата — качество ТЗ станет выше'}</p></div></div><div className="review"><p><span>Название</span><b>{form.title||'Не указано'}</b></p><p><span>Компания</span><b>{form.company||'Не указана'}</b></p><p><span>Вид работ</span><b>{form.category||'Не указан'}</b></p><p><span>Шаблон</span><b>{form.template||'Не выбран'}</b></p><p><span>Описание</span><b>{form.description||'Не добавлено'}</b></p></div></>}
  <div className="form-actions"><button className="secondary" onClick={()=>step===1?navigate('home'):setStep(s=>s-1)}>{step===1?'Отменить':'Назад'}</button><button className="primary" onClick={proceed}>{step===3?'Создать заявку':'Продолжить'}<ArrowRight size={18}/></button></div></section><Assistant compact/></div></main> }

function DetailPage({item,navigate,onRepeat}) { if(!item)return null; const events=[['Заявка создана',item.date,'Александра А.'],['Данные проверены системой','15 августа 2026','AI-помощник'],[item.status,item.status==='На согласовании'?'16 августа 2026':item.date,'Ответственное подразделение']]; return <div className="page-shell"><main className="wide-page detail-page embedded-page">
  <button className="back" onClick={()=>navigate('history')}><ArrowLeft size={17}/>К списку заявок</button>
  <div className="detail-header"><div><span className="eyebrow">{item.id}</span><h1>{item.title}</h1><p>{item.company}</p></div><span className={'badge '+item.tone}>{item.status}</span></div>
  <div className="detail-grid"><section className="detail-card"><h2>Информация о заявке</h2><dl><div><dt>Компания-заказчик</dt><dd>{item.company}</dd></div><div><dt>Вид работ</dt><dd>Инженерные работы</dd></div><div><dt>Дата создания</dt><dd>{item.date}</dd></div><div><dt>Желаемый срок</dt><dd>30 сентября 2026</dd></div><div><dt>Шаблон</dt><dd>Сопровождение инженерных работ</dd></div></dl><h3>Описание</h3><p className="description">Требуется сформировать комплект технических требований для выполнения работ и последующего согласования ответственным подразделением.</p><button className="primary" onClick={()=>onRepeat(item)}><Copy size={17}/>Создать похожую заявку</button></section>
  <section className="detail-card"><h2>История изменений</h2><div className="timeline">{events.map((e,i)=><div key={e[0]}><i>{i===events.length-1?<Clock3 size={15}/>:<Check size={15}/>}</i><span><b>{e[0]}</b><small>{e[1]} · {e[2]}</small></span></div>)}</div></section></div>
  </main><Assistant /></div> }

function Toast({toast,onClose}) { if(!toast)return null; return <div className={'toast '+toast.type}><span>{toast.type==='error'?'!':<Check size={17}/>}</span><b>{toast.text}</b><button onClick={onClose}><X size={16}/></button></div> }

export default function App(){ const [page,setPage]=useState('home'); const [repeat,setRepeat]=useState(null); const [selected,setSelected]=useState(null); const [toast,setToast]=useState(null); const notify=(text,type='success')=>setToast({text,type,id:Date.now()}); useEffect(()=>{if(!toast)return;const timer=setTimeout(()=>setToast(null),2600);return()=>clearTimeout(timer)},[toast]); const navigate=p=>{if(p==='create')setRepeat(null);setPage(p);window.scrollTo(0,0)}; const onRepeat=r=>{setRepeat(r);setPage('create');window.scrollTo(0,0)}; const onOpen=r=>{setSelected(r);setPage('detail');window.scrollTo(0,0)}; return <><Header page={page} navigate={navigate}/>{page==='home'&&<Home navigate={navigate} onRepeat={onRepeat} onOpen={onOpen}/>} {page==='history'&&<HistoryPage navigate={navigate} onRepeat={onRepeat} onOpen={onOpen}/>} {page==='create'&&<CreatePage navigate={navigate} initial={repeat} notify={notify}/>} {page==='detail'&&<DetailPage item={selected} navigate={navigate} onRepeat={onRepeat}/>}<Toast toast={toast} onClose={()=>setToast(null)}/><footer><span>ПРОСТОР · Корпоративная цифровая платформа</span><span>Поддержка&nbsp;&nbsp; · &nbsp;&nbsp;Версия 1.0</span></footer></> }
