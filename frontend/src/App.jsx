import { useMemo, useState } from 'react';
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

function Home({ navigate, onRepeat }) {
  return <div className="page-shell"><main className="main-content">
    <section className="welcome"><div><span className="eyebrow">ДОБРО ПОЖАЛОВАТЬ</span><h1>Добрый день, Александра!</h1><p>Создавайте заявки и следите за ходом их исполнения в одном месте.</p></div><div className="date"><CalendarDays size={18}/>17 августа, понедельник</div></section>
    <section className="hero-card"><div className="hero-copy"><div className="hero-icon"><FileText/></div><div><h2>Новая заявка</h2><p>Опишите задачу, выберите подходящий шаблон и получите готовый комплект документов.</p><button className="primary" onClick={()=>navigate('create')}><Plus size={19}/>Создать заявку<ArrowRight size={18}/></button></div></div><div className="hero-art"><span/><span/><span/><FileCheck2/></div></section>
    <section className="section-head"><div><h2>Последние заявки</h2><p>Недавние документы и их текущий статус</p></div><button className="link" onClick={()=>navigate('history')}>Вся история <ArrowRight size={17}/></button></section>
    <div className="request-list">{requestsSeed.slice(0,3).map(r=><RequestRow key={r.id} item={r} onRepeat={onRepeat}/>)}</div>
    <div className="stats"><div><span className="stat-icon blue"><FileText/></span><p><b>12</b>Всего заявок</p></div><div><span className="stat-icon green"><CheckCircle2/></span><p><b>8</b>Сформировано</p></div><div><span className="stat-icon orange"><Clock3/></span><p><b>3</b>В работе</p></div></div>
  </main><Assistant /></div>;
}

function RequestRow({item,onRepeat}) { return <article className="request-row"><div className="doc-icon"><FileText size={21}/></div><div className="request-info"><div><b>{item.title}</b><span className={'badge '+item.tone}>{item.status}</span></div><p>{item.id}<i/> {item.company}<i/> {item.date}</p></div><button className="repeat" onClick={()=>onRepeat(item)}><Copy size={16}/>Повторить</button><button className="round"><ArrowRight size={18}/></button></article> }

function HistoryPage({navigate,onRepeat}) { const [query,setQuery]=useState(''); const filtered=useMemo(()=>requestsSeed.filter(r=>(r.title+r.id+r.company).toLowerCase().includes(query.toLowerCase())),[query]); return <main className="wide-page">
  <button className="back" onClick={()=>navigate('home')}><ArrowLeft size={17}/>На главную</button><div className="title-row"><div><h1>История заявок</h1><p>Все созданные заявки и комплекты документов</p></div><button className="primary" onClick={()=>navigate('create')}><Plus size={18}/>Создать заявку</button></div>
  <div className="filterbar"><div className="search"><Search size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Поиск по номеру, названию или компании"/></div><button>Все статусы <ChevronDown size={16}/></button><button>За всё время <ChevronDown size={16}/></button></div>
  <div className="history-card"><div className="table-head"><span>Заявка</span><span>Дата создания</span><span>Статус</span><span/></div>{filtered.map(r=><div className="table-row" key={r.id}><div><div className="doc-icon"><FileText size={20}/></div><span><b>{r.title}</b><small>{r.id} · {r.company}</small></span></div><span>{r.date}</span><span><em className={'badge '+r.tone}>{r.status}</em></span><span><button className="repeat" onClick={()=>onRepeat(r)}><Copy size={16}/>Повторить</button><button className="round"><ArrowRight size={18}/></button></span></div>)}</div>
  <p className="count">Показано {filtered.length} из {requestsSeed.length} заявок</p>
  </main> }

const emptyForm = { title:'', company:'', category:'', deadline:'', description:'', template:'' };
function CreatePage({navigate,initial}) { const [form,setForm]=useState(initial ? {title:initial.title,company:initial.company,category:'Инженерные работы',deadline:'',description:'Требуется сформировать комплект документов для выполнения работ.',template:'Сопровождение инженерных работ'} : emptyForm); const [step,setStep]=useState(1); const [done,setDone]=useState(false); const set=(k,v)=>setForm(f=>({...f,[k]:v}));
  if(done) return <main className="success-screen"><div className="success-check"><Check size={38}/></div><h1>Заявка создана</h1><p>Черновик сохранён. Вы сможете вернуться к нему и дополнить данные в любое время.</p><strong>ЗА-2026-00432</strong><button className="primary" onClick={()=>navigate('history')}>Перейти к заявкам<ArrowRight size={18}/></button><button className="link" onClick={()=>navigate('home')}>На главную</button></main>;
  return <main className="form-page"><button className="back" onClick={()=>navigate(initial?'history':'home')}><ArrowLeft size={17}/>Назад</button><div className="form-heading"><div><span className="eyebrow">НОВАЯ ЗАЯВКА</span><h1>{initial?'Повтор заявки':'Создание заявки'}</h1><p>{initial?'Данные скопированы — проверьте и скорректируйте их.':'Заполните основные сведения — помощник подскажет на каждом этапе.'}</p></div><span>Черновик сохраняется автоматически</span></div>
  <div className="stepper">{['Основная информация','Требования и документы','Проверка'].map((s,i)=><div className={step>=i+1?'current':''} key={s}><i>{step>i+1?<Check size={14}/>:i+1}</i><span>{s}<small>{i===0?'О заявке':i===1?'Детали':'Подтверждение'}</small></span></div>)}</div>
  <div className="form-layout"><section className="form-card">
  {step===1 && <><h2>Основная информация</h2><p className="muted">Укажите, что требуется выполнить и для какой компании.</p><label>Название заявки <b>*</b><input value={form.title} onChange={e=>set('title',e.target.value)} placeholder="Например, разработка концепта обустройства"/></label><div className="field-grid"><label>Компания-заказчик <b>*</b><select value={form.company} onChange={e=>set('company',e.target.value)}><option value="">Выберите компанию</option><option>ПАО «Газпром нефть»</option><option>ООО «Газпромнефть-Заполярье»</option><option>АО «Газпромнефть-Ноябрьскнефтегаз»</option><option>ООО «Газпромнефть-Развитие»</option></select></label><label>Вид работ <b>*</b><select value={form.category} onChange={e=>set('category',e.target.value)}><option value="">Выберите вид работ</option><option>Инженерные работы</option><option>Проектирование</option><option>Геология</option><option>Разработка концепции</option></select></label></div><label>Краткое описание<textarea value={form.description} onChange={e=>set('description',e.target.value)} placeholder="Опишите задачу и ожидаемый результат"/></label></>}
  {step===2 && <><h2>Требования</h2><p className="muted">Выберите шаблон технического задания и укажите желаемый срок выполнения.</p><label>Шаблон технического задания <b>*</b><select value={form.template} onChange={e=>set('template',e.target.value)}><option value="">Выберите подходящий шаблон</option><option>Сопровождение инженерных работ</option><option>Интегрированный концепт развития</option><option>Концепт обустройства</option><option>Проектно-техническая документация</option></select></label><label>Желаемый срок выполнения<input type="date" value={form.deadline} onChange={e=>set('deadline',e.target.value)}/></label></>}
  {step===3 && <><h2>Проверьте данные</h2><p className="muted">Перед созданием заявки убедитесь, что всё заполнено верно.</p><div className="review"><p><span>Название</span><b>{form.title||'Не указано'}</b></p><p><span>Компания</span><b>{form.company||'Не указана'}</b></p><p><span>Вид работ</span><b>{form.category||'Не указан'}</b></p><p><span>Шаблон</span><b>{form.template||'Не выбран'}</b></p><p><span>Описание</span><b>{form.description||'Не добавлено'}</b></p></div></>}
  <div className="form-actions"><button className="secondary" onClick={()=>step===1?navigate('home'):setStep(s=>s-1)}>{step===1?'Отменить':'Назад'}</button><button className="primary" onClick={()=>step===3?setDone(true):setStep(s=>s+1)}>{step===3?'Создать заявку':'Продолжить'}<ArrowRight size={18}/></button></div></section><Assistant compact/></div></main> }

export default function App(){ const [page,setPage]=useState('home'); const [repeat,setRepeat]=useState(null); const navigate=p=>{if(p==='create')setRepeat(null);setPage(p);window.scrollTo(0,0)}; const onRepeat=r=>{setRepeat(r);setPage('create');window.scrollTo(0,0)}; return <><Header page={page} navigate={navigate}/>{page==='home'&&<Home navigate={navigate} onRepeat={onRepeat}/>} {page==='history'&&<HistoryPage navigate={navigate} onRepeat={onRepeat}/>} {page==='create'&&<CreatePage navigate={navigate} initial={repeat}/>}<footer><span>ПРОСТОР · Корпоративная цифровая платформа</span><span>Поддержка&nbsp;&nbsp; · &nbsp;&nbsp;Версия 1.0</span></footer></> }
