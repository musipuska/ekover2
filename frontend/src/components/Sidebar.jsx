import {
  LayoutDashboard,
  Upload,
  Database,
  Activity,
  FileChartColumn,
  Droplets,
  Gauge,
  Waves,
  ShieldCheck,
  BrainCircuit,
  Workflow,
} from "lucide-react";

const dashboardItems = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "water", label: "Water Quality", icon: Waves },
  { id: "quality", label: "Data Quality", icon: ShieldCheck },
  { id: "ml", label: "ML & Anomalies", icon: BrainCircuit },
  { id: "etl", label: "ETL Monitoring", icon: Workflow },
];

const managementItems = [
  { id: "dashboard", label: "Главная", icon: LayoutDashboard },
  { id: "upload", label: "Загрузка данных", icon: Upload },
  { id: "datasets", label: "Хранилище данных", icon: Database },
  { id: "processing", label: "Обработка данных", icon: Activity },
  { id: "analytics", label: "Анализ данных", icon: FileChartColumn },
];

function Group({ caption, items, activePage, onNavigate }) {
  return (
    <>
      <div className="menu-caption">{caption}</div>
      <nav className="navigation" aria-label={caption}>
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={activePage === item.id ? "nav-item active" : "nav-item"}
              aria-current={activePage === item.id ? "page" : undefined}
              onClick={() => onNavigate(item.id)}
            >
              <Icon size={19} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </>
  );
}

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon">
          <Droplets size={25} />
        </div>

        <div>
          <h2>ЭКОВЕР</h2>
          <span>Экологический мониторинг</span>
        </div>
      </div>

      <Group caption="АНАЛИТИКА" items={dashboardItems} activePage={activePage} onNavigate={onNavigate} />
      <Group caption="РАБОЧАЯ ОБЛАСТЬ" items={managementItems} activePage={activePage} onNavigate={onNavigate} />

      <div className="sidebar-bottom">
        <div className="connection-indicator"></div>
        <div>
          <strong>Система ЭКОВЕР</strong>
          <span>Локальная версия</span>
        </div>
      </div>
    </aside>
  );
}
