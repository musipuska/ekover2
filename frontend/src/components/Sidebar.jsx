import React from "react";
import {
  LayoutDashboard,
  Upload,
  Database,
  Activity,
  FileChartColumn,
  Droplets,
  BrainCircuit,
  AlertTriangle,
  History,
} from "lucide-react";

const menuItems = [
  {
    id: "dashboard",
    label: "Главная",
    icon: LayoutDashboard,
  },
  {
    id: "upload",
    label: "Загрузка данных",
    icon: Upload,
  },
  {
    id: "datasets",
    label: "Хранилище данных",
    icon: Database,
  },
  {
    id: "processing",
    label: "Обработка данных",
    icon: Activity,
  },
  {
    id: "analytics",
    label: "Анализ данных",
    icon: FileChartColumn,
  },
  {
    id: "ml",
    label: "Машинное обучение",
    icon: BrainCircuit,
  },
  {
    id: "anomalies",
    label: "Обнаруженные аномалии",
    icon: AlertTriangle,
  },
  {
    id: "history",
    label: "История запусков",
    icon: History,
  },
];

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

      <div className="menu-caption">РАБОЧАЯ ОБЛАСТЬ</div>

      <nav className="navigation">
        {menuItems.map((item) => {
          const Icon = item.icon;

          return (
            <button
              key={item.id}
              className={
                activePage === item.id
                  ? "nav-item active"
                  : "nav-item"
              }
              onClick={() => onNavigate(item.id)}
              type="button"
            >
              <Icon size={19} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

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