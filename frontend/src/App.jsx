import React, { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Database,
  FileSpreadsheet,
  Upload,
  RefreshCw,
  Search,
  CheckCircle2,
  Clock3,
  AlertCircle,
  FileChartColumn,
  Activity,
} from "lucide-react";

import Sidebar from "./components/Sidebar";
import StatCard from "./components/StatCard";
import { api } from "./services/api";

import "./style.css";

const pageTitles = {
  dashboard: "Главная",
  upload: "Загрузка данных",
  datasets: "Хранилище данных",
  processing: "Обработка данных",
  analytics: "Анализ данных",
};

function formatDate(value) {
  if (!value) return "—";

  return new Date(value).toLocaleString("ru-RU");
}

function Status({ value }) {
  const status = String(value || "unknown").toLowerCase();

  const labels = {
    queued: "Ожидает",
    running: "Выполняется",
    success: "Успешно",
    failed: "Ошибка",
    cancelled: "Отменено",
    unknown: "Неизвестно",
  };

  return (
    <span className={`status status-${status}`}>
      {labels[status] || status}
    </span>
  );
}

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState(null);
  const [selectedDataset, setSelectedDataset] = useState("");
  const [profile, setProfile] = useState(null);
  const [quality, setQuality] = useState(null);
  const [qualityError, setQualityError] = useState("");
  const [search, setSearch] = useState("");


  async function loadDatasets() {
    setLoading(true);
    setError("");

    try {
      const result = await api.getDatasets();

      setDatasets(
        Array.isArray(result)
          ? result
          : result.items || []
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDatasets();
  }, []);

  async function handleUpload(event) {
    event.preventDefault();

    if (!selectedFile) {
      setError("Сначала выбери CSV-файл.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");
    setUploadResult(null);

    try {
      const result = await api.uploadDataset(selectedFile);

      setUploadResult(result);
      setJobId(result.job_id || "");
      setSelectedDataset(result.dataset_id || "");
      setMessage("Файл успешно передан на сервер.");

      await loadDatasets();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function checkJob() {
    if (!jobId) {
      setError("Сначала загрузи файл, чтобы получить ID задачи.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await api.getJob(jobId);
      setJob(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }


  async function loadProfile(datasetId) {
    setSelectedDataset(datasetId);
    setProfile(null);
    setQuality(null);
    setQualityError("");
    setError("");
    setLoading(true);

    try {
      const profileResult = await api.getProfile(datasetId);

      setProfile(profileResult);

      try {
        const qualityResult = await api.getQuality(
          datasetId,
          profileResult.batch_id
        );

        setQuality(qualityResult);
      } catch (qualityErr) {
        setQualityError(qualityErr.message);
      }

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }


  const filteredDatasets = datasets.filter((dataset) => {
    const text = `${dataset.name || ""} ${dataset.id || ""}`;
    return text.toLowerCase().includes(search.toLowerCase());
  });

  const successfulDatasets = datasets.filter(
    (dataset) => dataset.status === "success"
  ).length;

  const renderDashboard = () => (
    <>
      <div className="welcome-panel">
        <div>
          <span className="eyebrow">ЭКОЛОГИЧЕСКИЙ МОНИТОРИНГ</span>
          <h2>Добро пожаловать в ЭКОВЕР</h2>
          <p>
            Единая система загрузки, хранения и обработки
            данных о качестве воды.
          </p>
        </div>

        <div className="welcome-icon">
          <Database size={55} />
        </div>
      </div>

      <div className="stats-grid">
        <StatCard
          title="Наборы данных"
          value={datasets.length}
          description="Всего зарегистрировано"
          icon={Database}
        />

        <StatCard
          title="Успешные наборы"
          value={successfulDatasets}
          description="По статусу в базе данных"
          icon={CheckCircle2}
        />

        <StatCard
          title="Последняя загрузка"
          value={datasets.length ? "Есть" : "Нет"}
          description="Наличие загруженных данных"
          icon={FileSpreadsheet}
        />
      </div>

      <section className="content-card">
        <div className="section-heading">
          <div>
            <h3>Последние наборы данных</h3>
            <p>Недавно зарегистрированные файлы</p>
          </div>

          <button
            className="secondary-button"
            onClick={() => setActivePage("datasets")}
          >
            Все наборы
          </button>
        </div>

        {datasets.length === 0 ? (
          <div className="empty-state">
            <Database size={36} />
            <strong>Данных пока нет</strong>
            <span>Загрузи первый CSV-файл.</span>
          </div>
        ) : (
          <DatasetTable
            datasets={datasets.slice(0, 5)}
            onSelect={loadProfile}
          />
        )}
      </section>
    </>
  );

  const renderUpload = () => (
    <section className="content-card upload-card">
      <div className="section-heading">
        <div>
          <h3>Загрузка нового набора данных</h3>
          <p>Выбери CSV-файл для сохранения в системе.</p>
        </div>
        <Upload size={25} />
      </div>

      <form onSubmit={handleUpload}>
        <label className="file-drop">
          <Upload size={35} />
          <strong>
            {selectedFile
              ? selectedFile.name
              : "Выбери CSV-файл"}
          </strong>
          <span>Нажми, чтобы выбрать файл на компьютере</span>

          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(event) =>
              setSelectedFile(event.target.files[0] || null)
            }
          />
        </label>

        <button
          className="primary-button"
          type="submit"
          disabled={loading || !selectedFile}
        >
          <Upload size={18} />
          Загрузить данные
        </button>
      </form>

      {uploadResult && (
        <div className="result-panel">
          <h4>Результат загрузки</h4>
          <p>Файл: {uploadResult.filename}</p>
          <p>Статус: <Status value={uploadResult.status} /></p>
          <p>Dataset ID: <code>{uploadResult.dataset_id}</code></p>
          <p>Version ID: <code>{uploadResult.version_id}</code></p>
          <p>Job ID: <code>{uploadResult.job_id}</code></p>
          <p>Batch ID: <code>{uploadResult.batch_id}</code></p>
          <p>{uploadResult.message}</p>
        </div>
      )}
    </section>
  );

  const renderDatasets = () => (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h3>Хранилище данных</h3>
          <p>Все зарегистрированные наборы данных.</p>
        </div>

        <button
          className="icon-button"
          onClick={loadDatasets}
          title="Обновить"
        >
          <RefreshCw size={19} />
        </button>
      </div>

      <div className="search-field">
        <Search size={18} />
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Поиск по названию или ID..."
        />
      </div>

      <DatasetTable
        datasets={filteredDatasets}
        onSelect={loadProfile}
      />
    </section>
  );

  const renderProcessing = () => (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h3>Статус обработки</h3>
          <p>Проверка состояния ETL-задачи.</p>
        </div>
        <Activity size={25} />
      </div>

      <label className="field-label">Идентификатор задачи (Job ID)</label>

      <input
        className="text-input"
        value={jobId}
        onChange={(event) => setJobId(event.target.value)}
        placeholder="Вставь Job ID после загрузки файла"
      />

      <button
        className="primary-button"
        onClick={checkJob}
        disabled={loading || !jobId}
      >
        <RefreshCw size={18} />
        Проверить статус
      </button>

      {job && (
        <div className="result-panel">
          <h4>Информация о задаче</h4>
          <p>ID задачи: <code>{job.id}</code></p>
          <p>Статус: <Status value={job.status} /></p>
          {job.error_message && (
            <p className="error-text">
              {job.error_message}
            </p>
          )}
        </div>
      )}

      <div className="notice">
        <Clock3 size={20} />
        <p>
          Сейчас ETL запускается отдельно из терминала.
          После ручного запуска здесь можно проверить,
          обновился ли статус задачи в базе данных.
        </p>
      </div>
    </section>
  );

  const renderAnalytics = () => (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h3>Анализ данных</h3>
          <p>Просмотр профиля обработанного набора.</p>
        </div>
        <FileChartColumn size={25} />
      </div>

      <label className="field-label">Выбери набор данных</label>

      <select
        className="text-input"
        value={selectedDataset}
        onChange={(event) => {
          if (event.target.value) {
            loadProfile(event.target.value);
          } else {
            setProfile(null);
            setQuality(null);
            setQualityError("");
            setSelectedDataset("");
          }
        }}
      >
        <option value="">Выбрать набор данных</option>

        {datasets.map((dataset) => (
          <option key={dataset.id} value={dataset.id}>
            {dataset.name || dataset.id}
          </option>
        ))}
      </select>

      
{profile && (
  <div className="profile-result">
    <div className="stats-grid">
      <StatCard
        title="Количество строк"
        value={profile.row_count ?? "—"}
        description="Записей в наборе"
        icon={Database}
      />

      <StatCard
        title="Количество столбцов"
        value={profile.column_count ?? "—"}
        description="Полей в наборе"
        icon={FileSpreadsheet}
      />
    </div>

    <h4>Профиль столбцов</h4>

    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Столбец</th>
            <th>Тип данных</th>
            <th>Пропуски</th>
            <th>Пропуски, %</th>
            <th>Уникальные</th>
            <th>Минимум</th>
            <th>Максимум</th>
            <th>Среднее</th>
          </tr>
        </thead>

        <tbody>
          {(profile.columns || []).map((column) => (
            <tr key={column.name}>
              <td>{column.name}</td>
              <td>{column.data_type}</td>
              <td>{column.null_count}</td>
              <td>{column.null_percent?.toFixed(2) ?? "—"}%</td>
              <td>{column.unique_count}</td>
              <td>{column.min_value ?? "—"}</td>
              <td>{column.max_value ?? "—"}</td>
              <td>
                {column.average_value == null
                  ? "—"
                  : Number(column.average_value).toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>

    <h4>Отчёт качества данных</h4>

      {quality ? (
        <>
          <div className="stats-grid">
            <StatCard
              title="Строк в Bronze"
              value={quality.bronze_rows}
              description="До очистки"
              icon={Database}
            />

            <StatCard
              title="Строк в Silver"
              value={quality.silver_rows}
              description="После очистки"
              icon={CheckCircle2}
            />

            <StatCard
              title="Удалено дубликатов"
              value={quality.removed_duplicates}
              description="Полные дубликаты"
              icon={RefreshCw}
            />

            <StatCard
              title="Пустые значения"
              value={quality.null_cells_after_cleaning}
              description="После очистки"
              icon={AlertCircle}
            />
          </div>

          <div className="result-panel">
            <h4>Результат проверки качества</h4>
            <p>
              Статус:{" "}
              <Status value={quality.quality_status} />
            </p>
            <p>
              Batch ID: <code>{quality.batch_id}</code>
            </p>
          </div>
        </>
      ) : (
        <div className="notice">
          <AlertCircle size={20} />
          <p>
            {qualityError || "Отчёт качества пока недоступен."}
          </p>
        </div>
      )}
    </div>
  )}

    </section>
  );

  return (
    <div className="app-layout">
      <Sidebar
        activePage={activePage}
        onNavigate={(page) => {
          setActivePage(page);
          setError("");
          setMessage("");
        }}
      />

      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="topbar-caption">РАБОЧАЯ ПАНЕЛЬ</span>
            <h1>{pageTitles[activePage]}</h1>
          </div>

          <div className="system-label">
            <span className="system-dot"></span>
            Локальная система
          </div>
        </header>

        <div className="page-content">
          {error && (
            <div className="alert alert-error">
              <AlertCircle size={19} />
              {error}
            </div>
          )}

          {message && (
            <div className="alert alert-success">
              <CheckCircle2 size={19} />
              {message}
            </div>
          )}

          {loading && (
            <div className="loading-label">
              <RefreshCw size={16} />
              Выполняется запрос...
            </div>
          )}

          {activePage === "dashboard" && renderDashboard()}
          {activePage === "upload" && renderUpload()}
          {activePage === "datasets" && renderDatasets()}
          {activePage === "processing" && renderProcessing()}
          {activePage === "analytics" && renderAnalytics()}
        </div>
      </main>
    </div>
  );
}

function DatasetTable({ datasets, onSelect }) {
  if (!datasets.length) {
    return (
      <div className="empty-state">
        <Database size={35} />
        <strong>Наборы данных не найдены</strong>
        <span>Загрузи CSV-файл, чтобы он появился здесь.</span>
      </div>
    );
  }

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Название</th>
            <th>Статус</th>
            <th>Дата создания</th>
            <th>Действие</th>
          </tr>
        </thead>

        <tbody>
          {datasets.map((dataset) => (
            <tr key={dataset.id}>
              <td>
                <div className="dataset-name">
                  <FileSpreadsheet size={19} />
                  <div>
                    <strong>{dataset.name || "Без названия"}</strong>
                    <span>{dataset.id}</span>
                  </div>
                </div>
              </td>

              <td><Status value={dataset.status} /></td>

              <td>{formatDate(dataset.created_at)}</td>

              <td>
                <button
                  className="table-action"
                  onClick={() => onSelect(dataset.id)}
                >
                  Профиль
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}