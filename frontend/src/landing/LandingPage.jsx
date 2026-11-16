import React, { useEffect, useState } from 'react';
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, Atom, BarChart3,
  Check, CheckCircle2, CircleDot, Database, Droplets,
  FileCheck2, FileSpreadsheet, GitBranch, Layers3, Menu, Microscope,
  Network, ScanSearch, ShieldCheck, Waves, X, Zap,
} from 'lucide-react';

const nav = [
  ['Возможности', '#features'], ['Как работает', '#workflow'],
  ['Технологии', '#technology'], ['О проекте', '#about'],
];

const features = [
  { icon: FileSpreadsheet, n: '01', title: 'Загрузка и валидация', text: 'Принимайте CSV-наборы, проверяйте структуру и формат до запуска обработки.', tag: 'CSV · schema check' },
  { icon: Layers3, n: '02', title: 'Сквозной ETL-процесс', text: 'Проводите данные через последовательные слои RAW, BRONZE, SILVER и GOLD.', tag: 'RAW → GOLD' },
  { icon: ScanSearch, n: '03', title: 'Профилирование данных', text: 'Изучайте структуру, типы, пропуски, уникальные значения и статистики измерений.', tag: 'Data profiling' },
  { icon: ShieldCheck, n: '04', title: 'Контроль качества', text: 'Получайте сводный статус, находите дубликаты и пропуски, отслеживайте проблемные записи.', tag: 'Quality Gate' },
  { icon: Network, n: '05', title: 'REST API', text: 'Подключайте обработку и результаты анализа к внешним сервисам и рабочим процессам.', tag: 'API-first' },
  { icon: GitBranch, n: '06', title: 'Версии и история', text: 'Сохраняйте историю наборов и задач, чтобы контролировать путь данных от загрузки до результата.', tag: 'Traceability' },
];

const steps = [
  ['01', 'Загрузка', 'CSV-файл или набор измерений поступает в систему.', FileSpreadsheet],
  ['02', 'Проверка', 'Проверяем формат, структуру и обязательные поля.', FileCheck2],
  ['03', 'Обработка', 'Последовательно преобразуем данные в ETL-слоях.', Layers3],
  ['04', 'Аналитика', 'Формируем профиль и отчёт о качестве данных.', BarChart3],
  ['05', 'Результат', 'Открываем результаты в интерфейсе и через API.', Activity],
];

const tech = ['Python', 'FastAPI', 'React', 'Pandas', 'PySpark', 'Parquet', 'Docker', 'Airflow', 'SQLAlchemy', 'Alembic', 'Vite'];

function useReveal() {
  useEffect(() => {
    const nodes = document.querySelectorAll('[data-reveal]');
    if (!('IntersectionObserver' in window)) {
      nodes.forEach((node) => node.classList.add('is-visible'));
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);
}

function Brand({ footer = false }) {
  return <a className={`brand ${footer ? 'brand-footer' : ''}`} href="#top" aria-label="ЭКОВЕР — на главную">
    <span className="brand-mark"><Droplets size={20} strokeWidth={2.1} /></span>
    <span>ЭКО<span className="brand-light">ВЕР</span><small>WATER DATA INTELLIGENCE</small></span>
  </a>;
}

function WaterOrb() {
  // Замена тяжёлой WebGL-сцены: SVG particle-orb с CSS-анимацией.
  // Prompt для будущего 3D-арта: "cinematic photorealistic translucent water droplet made of
  // thousands of tiny cyan particles and fine data lines, deep navy background, teal rim light,
  // premium environmental technology campaign, volumetric lighting, no text, 3D render".
  const particles = Array.from({ length: 42 }, (_, i) => {
    const angle = (i * 137.5 * Math.PI) / 180;
    const radius = 22 + ((i * 17) % 105);
    return { x: 180 + Math.cos(angle) * radius * 0.78, y: 170 + Math.sin(angle) * radius, r: 1.2 + (i % 4) * 0.45, delay: `${(i % 9) * -0.4}s` };
  });
  return <div className="orb-scene" aria-label="Абстрактная визуализация капли воды и цифровых данных" role="img">
    <div className="orb-halo halo-one" /><div className="orb-halo halo-two" />
    <svg className="water-orb" viewBox="0 0 360 360" fill="none" aria-hidden="true">
      <defs>
        <radialGradient id="dropFill" cx="0" cy="0" r="1" gradientTransform="translate(144 118) rotate(54) scale(210)"><stop stopColor="#D9FFF7" stopOpacity=".72"/><stop offset=".32" stopColor="#38BDF8" stopOpacity=".3"/><stop offset="1" stopColor="#0D9488" stopOpacity=".05"/></radialGradient>
        <linearGradient id="dropStroke" x1="70" y1="48" x2="292" y2="300"><stop stopColor="#D6FFF8"/><stop offset=".42" stopColor="#2DD4BF"/><stop offset="1" stopColor="#38BDF8" stopOpacity=".25"/></linearGradient>
        <clipPath id="dropClip"><path d="M180 32C180 32 64 170 64 226a116 116 0 0 0 232 0C296 170 180 32 180 32Z"/></clipPath>
      </defs>
      <path d="M180 32C180 32 64 170 64 226a116 116 0 0 0 232 0C296 170 180 32 180 32Z" fill="url(#dropFill)" stroke="url(#dropStroke)" strokeWidth="1.4" />
      <g clipPath="url(#dropClip)">
        <path d="M43 180C104 140 160 220 218 177s84-31 124-10M37 220c66-38 104 41 169 5s99-33 137-4M45 259c63-26 103 30 161 6s94-19 131 0" stroke="#8CF7E8" strokeOpacity=".38" strokeWidth=".8"/>
        <path d="M65 135h230M58 158h244M52 286h255" stroke="#38BDF8" strokeOpacity=".22" strokeDasharray="2 6"/>
        {particles.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r={p.r} fill={i % 3 === 0 ? '#A3E635' : '#9AF7EB'} opacity={.32 + (i % 5) * .12} />)}
      </g>
      <path d="M180 32C180 32 64 170 64 226a116 116 0 0 0 232 0C296 170 180 32 180 32Z" stroke="#B9FFF4" strokeOpacity=".34" strokeWidth=".7"/>
      <path d="M123 119c14-20 29-37 42-49" stroke="white" strokeOpacity=".65" strokeWidth="2" strokeLinecap="round"/>
    </svg>
    <div className="orb-label label-top"><span className="live-dot"/> LIVE DATA STREAM</div>
    <div className="orb-label label-bottom"><span>pH</span><b>7.24</b><i>●</i><span>IN RANGE</span></div>
    <div className="orb-coordinate">55°45' N&nbsp; 37°37' E</div>
  </div>;
}

function DashboardMock() {
  const bars = [38, 46, 42, 55, 49, 62, 58, 68, 61, 77, 72, 86, 78, 92, 83, 96, 88, 100, 91, 106, 98, 115, 104, 122];
  return <div className="dashboard-shell" data-reveal>
    <div className="dash-top"><div className="dash-brand"><span className="dash-dot"/> ЭКОВЕР <small>/ ANALYTICS</small></div><div className="dash-top-right"><span className="dash-period">Последние 30 дней⌄</span><span className="dash-avatar">А</span></div></div>
    <div className="dash-content">
      <div className="dash-heading"><div><span className="dash-eyebrow">ОБЗОР ДАННЫХ</span><h3>Мониторинг качества воды</h3><p>Сводная информация по загруженным измерениям</p></div><span className="dash-status"><i/> Система активна</span></div>
      <div className="metric-row">
        <div className="metric-card"><span>Записей обработано</span><strong>24 860</strong><small><b>↗ 12.8%</b> к прошлому периоду</small><Database className="metric-icon" size={17}/></div>
        <div className="metric-card"><span>Полнота данных</span><strong>98.6<span>%</span></strong><small><b>↗ 2.4%</b> к прошлому периоду</small><CheckCircle2 className="metric-icon" size={17}/></div>
        <div className="metric-card"><span>Статус качества</span><strong className="gold-value">GOLD</strong><small><b>●</b> Проверки пройдены</small><ShieldCheck className="metric-icon" size={17}/></div>
      </div>
      <div className="dash-grid">
        <div className="chart-card"><div className="chart-title"><div><b>Динамика измерений</b><small>Количество валидных записей</small></div><span>24ч&nbsp; 7д&nbsp; <b>30д</b></span></div><div className="chart-area"><div className="chart-y"><span>1.2k</span><span>900</span><span>600</span><span>300</span><span>0</span></div><div className="chart-plot"><div className="chart-gridlines"><i/><i/><i/><i/><i/></div><div className="bar-series">{bars.map((h, i) => <i key={i} style={{ height: `${h}px`, opacity: .42 + (i / bars.length) * .5 }}/>)}</div><div className="chart-x"><span>01 ноя</span><span>08 ноя</span><span>15 ноя</span><span>22 ноя</span><span>30 ноя</span></div></div></div></div>
        <div className="quality-card"><div className="chart-title"><div><b>Состав набора</b><small>Проверка качества</small></div><CircleDot size={17}/></div><div className="quality-ring"><div><strong>98.6%</strong><span>валидных данных</span></div></div><div className="quality-legend"><span><i className="q-valid"/>Валидные <b>98.6%</b></span><span><i className="q-warn"/>Пропуски <b>1.1%</b></span><span><i className="q-error"/>Дубликаты <b>0.3%</b></span></div></div>
      </div>
      <div className="dash-table"><div className="table-heading"><b>Профиль параметров</b><span>Открыть отчёт <ArrowUpRight size={13}/></span></div><div className="table-row table-head"><span>Параметр</span><span>Измерений</span><span>Среднее</span><span>Мин. / Макс.</span><span>Статус</span></div><div className="table-row"><span><i className="param-dot cyan"/> pH</span><span>8 240</span><span>7.24</span><span>6.8 / 8.1</span><em>В норме</em></div><div className="table-row"><span><i className="param-dot blue"/> Температура</span><span>8 310</span><span>18.6 °C</span><span>12.2 / 24.8</span><em>В норме</em></div><div className="table-row"><span><i className="param-dot lime"/> Мутность</span><span>8 310</span><span>1.42 NTU</span><span>0.4 / 3.8</span><em>В норме</em></div></div>
    </div>
    <div className="dash-foot"><span><span className="live-dot"/> Данные обновлены</span><span>DEMO DATA · НЕ ФАКТИЧЕСКИЕ ПОКАЗАТЕЛИ</span></div>
  </div>;
}

export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [form, setForm] = useState({ name: '', email: '', org: '' });
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  useReveal();

  useEffect(() => {
    const onScroll = () => document.querySelector('.site-nav')?.classList.toggle('nav-scrolled', window.scrollY > 24);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const update = (key) => (event) => setForm((old) => ({ ...old, [key]: event.target.value }));
  const submit = (event) => {
    event.preventDefault();
    if (!form.name.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      setError('Укажите имя и корректный email — это обязательные поля.');
      return;
    }
    setError('');
    setSubmitted(true);
  };

  return <div className="landing" id="top">
    <div className="ambient ambient-a"/><div className="ambient ambient-b"/>
    <header className="site-nav">
      <div className="nav-inner"><Brand />
        <nav className={menuOpen ? 'nav-links open' : 'nav-links'} aria-label="Основная навигация">
          {nav.map(([label, href]) => <a key={href} href={href} onClick={() => setMenuOpen(false)}>{label}</a>)}
          <a className="mobile-nav-cta" href="#contact" onClick={() => setMenuOpen(false)}>Запросить демо <ArrowUpRight size={15}/></a>
        </nav>
        <a className="nav-cta" href="#contact">Запросить демо <ArrowUpRight size={15}/></a>
        <button className="burger" onClick={() => setMenuOpen(!menuOpen)} aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'} aria-expanded={menuOpen}>{menuOpen ? <X/> : <Menu/>}</button>
      </div>
    </header>

    <main>
      <section className="hero section-wrap">
        <div className="hero-copy">
          <div className="eyebrow-pill"><span className="live-dot"/> DATA FOR A CLEARER FUTURE</div>
          <h1>Чистая вода<br/>начинается с <span>чистых данных.</span></h1>
          <p className="hero-lead">ЭКОВЕР объединяет загрузку, обработку и анализ данных о качестве воды — от исходного измерения до понятного аналитического результата.</p>
          <div className="hero-actions"><a className="button-primary" href="#contact">Запросить демо <ArrowUpRight size={17}/></a><a className="button-ghost" href="#workflow"><span className="play-icon">▶</span> Как это работает</a></div>
          <div className="hero-proof"><span><Check size={14}/> Контроль качества данных</span><span><Check size={14}/> Сквозная обработка</span><span><Check size={14}/> Аналитика в одном месте</span></div>
        </div>
        <WaterOrb />
        <div className="hero-bottomline"><span>01 / ПЛАТФОРМА МОНИТОРИНГА</span><span>ОТ ИЗМЕРЕНИЯ К ПОНИМАНИЮ <ArrowDownRight size={14}/></span></div>
      </section>

      <section className="signal-strip"><div className="signal-inner"><div><span className="signal-icon"><Layers3 size={16}/></span><b>RAW <i>→</i> BRONZE <i>→</i> SILVER <i>→</i> GOLD</b><small>Сквозной ETL</small></div><div><span className="signal-icon"><Zap size={16}/></span><b>REST API</b><small>Интеграция</small></div><div><span className="signal-icon"><FileSpreadsheet size={16}/></span><b>CSV <i>→</i> PARQUET</b><small>Работа с данными</small></div><div><span className="signal-icon"><ShieldCheck size={16}/></span><b>DATA QUALITY</b><small>Контроль качества</small></div></div></section>

      <section className="trust section-wrap" id="about" data-reveal><p>СОЗДАНО ДЛЯ ТЕХ, КТО РАБОТАЕТ С ДАННЫМИ О ВОДЕ</p><div className="trust-list"><span><Waves/> Водоканалы и экослужбы</span><span><Microscope/> Научные лаборатории</span><span><BarChart3/> Аналитические команды</span><span><Atom/> Инженеры данных</span></div></section>

      <section className="problem section-wrap">
        <div className="section-intro" data-reveal><span className="section-kicker">01 — ЗАЧЕМ НУЖЕН ЭКОВЕР</span><h2>Данные должны<br/>работать <span>на решение.</span></h2></div>
        <div className="problem-content" data-reveal><p className="problem-lead">Измерения поступают из разных источников. Форматы отличаются, в данных встречаются пропуски и дубликаты, а подготовка к анализу отнимает время.</p><div className="problem-flow"><div><span className="problem-number">01</span><b>Разрозненные источники</b><small>Файлы, датчики, разные форматы</small></div><ArrowRight/><div><span className="problem-number">02</span><b>Ручная подготовка</b><small>Проверки и очистка вручную</small></div><ArrowRight/><div className="problem-solution"><span className="problem-number">03</span><b>ЭКОВЕР</b><small>Единый управляемый процесс</small></div></div></div>
      </section>

      <section className="features section-wrap" id="features">
        <div className="section-header" data-reveal><div><span className="section-kicker">02 — ВОЗМОЖНОСТИ</span><h2>Весь путь данных.<br/><span>Под контролем.</span></h2></div><p>Инструменты, которые помогают превратить исходные измерения в структурированные, проверенные и готовые к анализу данные.</p></div>
        <div className="feature-grid">{features.map(({ icon: Icon, n, title, text, tag }) => <article className="feature-card" key={n} data-reveal><div className="feature-top"><span className="feature-icon"><Icon size={20}/></span><span className="feature-number">{n}</span></div><h3>{title}</h3><p>{text}</p><div className="feature-tag"><span/> {tag} <ArrowUpRight size={13}/></div></article>)}</div>
      </section>

      <section className="workflow section-wrap" id="workflow">
        <div className="section-header" data-reveal><div><span className="section-kicker">03 — КАК ЭТО РАБОТАЕТ</span><h2>Пять шагов.<br/><span>Один поток данных.</span></h2></div><p>Понятная последовательность от загрузки файла до готового результата — с контролем на каждом этапе.</p></div>
        <div className="workflow-track"><div className="workflow-line"/><div className="workflow-progress"/>{steps.map(([num, title, text, Icon]) => <div className="workflow-step" key={num} data-reveal><span className="step-index">{num}</span><span className="step-icon"><Icon size={21}/></span><h3>{title}</h3><p>{text}</p></div>)}</div>
      </section>

      <section className="visual section-wrap"><div className="visual-copy" data-reveal><span className="section-kicker">04 — ЕДИНАЯ КАРТИНА</span><h2>От потока измерений<br/>к <span>ясной аналитике.</span></h2><p>Сводные показатели, профиль параметров и статус качества — в одном интерфейсе. Пример того, как могут выглядеть результаты обработки.</p><a href="#contact" className="text-link">Посмотреть демо <ArrowUpRight size={16}/></a><div className="visual-note"><span className="live-dot"/> Демонстрационные данные интерфейса</div></div><DashboardMock/></section>

      <section className="technology section-wrap" id="technology"><div className="tech-heading" data-reveal><span className="section-kicker">05 — ТЕХНОЛОГИЧЕСКАЯ ОСНОВА</span><h2>Инженерия, которая<br/><span>работает с данными.</span></h2></div><div className="tech-marquee" aria-label="Технологии"><div className="tech-track">{[...tech, ...tech].map((item, i) => <span key={`${item}-${i}`}><i/> {item}</span>)}</div></div><p className="tech-caption">Современный стек для обработки, хранения и представления данных.</p></section>

      <section className="architecture section-wrap"><div className="section-header" data-reveal><div><span className="section-kicker">06 — АРХИТЕКТУРА ДАННЫХ</span><h2>Слои, которые<br/><span>создают порядок.</span></h2></div><p>Многоэтапная обработка помогает сохранять происхождение данных и последовательно повышать их готовность к аналитике.</p></div><div className="layer-stack" data-reveal><div className="layer-caption"><span>DATA LIFECYCLE</span><span>СЛЕВА НАПРАВО · ОТ ИСХОДНЫХ ДАННЫХ К ВИТРИНАМ</span></div><div className="layers"><div className="layer layer-raw"><small>01 / SOURCE</small><b>RAW</b><span>Исходные данные</span><ArrowRight/></div><div className="layer layer-bronze"><small>02 / INGEST</small><b>BRONZE</b><span>Загруженные данные</span><ArrowRight/></div><div className="layer layer-silver"><small>03 / CLEAN</small><b>SILVER</b><span>Очищенные данные</span><ArrowRight/></div><div className="layer layer-gold"><small>04 / ANALYTICS</small><b>GOLD</b><span>Данные для анализа</span><CheckCircle2/></div></div><div className="layer-foot"><span><CircleDot size={13}/> Контроль качества между этапами</span><span><GitBranch size={13}/> Версионирование обработки</span><span><Database size={13}/> Структурированные результаты</span></div></div></section>

      <section className="roadmap section-wrap"><div className="roadmap-copy" data-reveal><span className="section-kicker">07 — РАЗВИТИЕ ПЛАТФОРМЫ</span><h2>Система, которая<br/><span>будет расти.</span></h2><p>ЭКОВЕР развивается как исследовательский программный комплекс. Следующие направления расширят возможности хранения, оркестрации и интеллектуального анализа.</p></div><div className="roadmap-list" data-reveal><div><span className="roadmap-status status-progress">В РАЗВИТИИ</span><b>PostgreSQL и расширение хранения</b><small>Развитие надёжной работы с наборами и метаданными</small><ArrowUpRight/></div><div><span className="roadmap-status">ПЛАНИРУЕТСЯ</span><b>Распределённая обработка</b><small>Масштабирование работы с большими объёмами данных</small><ArrowUpRight/></div><div><span className="roadmap-status">ПЛАНИРУЕТСЯ</span><b>Оркестрация Airflow</b><small>Автоматизация расписаний и зависимостей процессов</small><ArrowUpRight/></div><div><span className="roadmap-status">ИССЛЕДОВАНИЕ</span><b>ML-коррекция показаний</b><small>Методы выявления аномалий и анализа сигналов датчиков</small><ArrowUpRight/></div></div></section>

      <section className="contact section-wrap" id="contact"><div className="contact-glow"/><div className="contact-copy" data-reveal><span className="section-kicker">08 — СЛЕДУЮЩИЙ ШАГ</span><h2>Давайте посмотрим,<br/>что <span>могут ваши данные.</span></h2><p>Расскажите о вашей задаче — покажем возможности ЭКОВЕР и обсудим сценарий использования.</p><div className="contact-aside"><span><CheckCircle2 size={16}/> Демонстрация платформы</span><span><CheckCircle2 size={16}/> Обсуждение интеграции</span></div></div><div className="contact-form-wrap" data-reveal>{submitted ? <div className="form-success"><span><CheckCircle2 size={30}/></span><h3>Спасибо за интерес к ЭКОВЕР.</h3><p>Форма работает в демонстрационном режиме. Подключение отправки заявок на сервер добавим при интеграции с backend.</p><button className="button-ghost" onClick={() => setSubmitted(false)}>Отправить ещё раз</button></div> : <form className="contact-form" onSubmit={submit} noValidate><div className="form-title"><b>Запросить демонстрацию</b><span>Поля со звёздочкой обязательны</span></div><label>Ваше имя <i>*</i><input value={form.name} onChange={update('name')} placeholder="Как к вам обращаться?" autoComplete="name"/></label><label>Рабочий email <i>*</i><input type="email" value={form.email} onChange={update('email')} placeholder="name@company.ru" autoComplete="email"/></label><label>Организация<input value={form.org} onChange={update('org')} placeholder="Название организации" autoComplete="organization"/></label>{error && <p className="form-error" role="alert">{error}</p>}<button className="button-primary form-submit" type="submit">Отправить запрос <ArrowUpRight size={17}/></button><small className="form-legal">Нажимая кнопку, вы соглашаетесь на обработку указанных данных для связи по вашему запросу.</small></form>}</div></section>
    </main>

    <footer className="footer"><div className="footer-main"><div><Brand footer/><p>Данные о воде —<br/>в ясной и управляемой системе.</p></div><div className="footer-links"><div><b>ПЛАТФОРМА</b><a href="#features">Возможности</a><a href="#workflow">Как работает</a><a href="#technology">Технологии</a></div><div><b>ПРОЕКТ</b><a href="#about">О проекте</a><a href="#contact">Запросить демо</a><a href="https://github.com/musipuska/ekover2" target="_blank" rel="noreferrer">GitHub <ArrowUpRight size={12}/></a></div></div></div><div className="footer-bottom"><span>© 2026 ЭКОВЕР · ПРОГРАММНЫЙ КОМПЛЕКС МОНИТОРИНГА КАЧЕСТВА ВОДЫ</span><a href="#top">НАВЕРХ ↑</a></div></footer>
  </div>;
}
