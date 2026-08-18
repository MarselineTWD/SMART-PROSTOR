const paths = {
  plus: <><path d="M12 5v14M5 12h14"/></>, arrowRight:<><path d="m9 18 6-6-6-6"/></>, arrowLeft:<><path d="m15 18-6-6 6-6"/></>,
  file:<><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5M9 12h6M9 16h6"/></>, check:<path d="m5 12 4 4L19 6"/>,
  search:<><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>, send:<path d="m3 3 18 9-18 9 4-9zM7 12h14"/>,
  user:<><circle cx="12" cy="8" r="4"/><path d="M4 22c0-5 3-8 8-8s8 3 8 8"/></>,
  clock:<><circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/></>, calendar:<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/></>,
  chat:<><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/></>, bot:<><rect x="4" y="7" width="16" height="13" rx="3"/><path d="M12 3v4M8 12h.01M16 12h.01M8 16h8"/></>,
  history:<><path d="M3 12a9 9 0 1 0 3-7M3 4v6h6M12 7v6l4 2"/></>, home:<><path d="m3 11 9-8 9 8v10H3zM9 21v-7h6v7"/></>,
  copy:<><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V4H4v12h4"/></>, attach:<><path d="m21 11-9 9a6 6 0 0 1-8-8l10-10a4 4 0 0 1 6 6L10 18a2 2 0 0 1-3-3l9-9"/></>,
  menu:<path d="M4 7h16M4 12h16M4 17h16"/>, close:<path d="m6 6 12 12M18 6 6 18"/>, down:<path d="m6 9 6 6 6-6"/>, spark:<path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5z"/>
};
function Icon({size=24, children, ...props}){return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{children}</svg>}
const make = key => props => <Icon {...props}>{paths[key] || paths.file}</Icon>;
export const ArrowLeft=make('arrowLeft'),ArrowRight=make('arrowRight'),Bot=make('bot'),BriefcaseBusiness=make('file'),CalendarDays=make('calendar'),Check=make('check'),CheckCircle2=make('check'),ChevronDown=make('down'),CircleUserRound=make('user'),Clock3=make('clock'),Copy=make('copy'),FileCheck2=make('file'),FileText=make('file'),History=make('history'),LayoutDashboard=make('home'),Menu=make('menu'),MessageCircleQuestion=make('chat'),Paperclip=make('attach'),Plus=make('plus'),Search=make('search'),Send=make('send'),Sparkles=make('spark'),X=make('close');
