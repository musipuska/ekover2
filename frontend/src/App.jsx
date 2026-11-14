
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
  BrainCircuit,
  Play,
  ShieldAlert,
  History,
  BarChart3,
} from "lucide-react";

import Sidebar from "./components/Sidebar";
import StatCard from "./components/StatCard";
import { api } from "./services/api";

import "./style.css";

const API_ML = "http://127.0.0.1:8000/api/v1/ml";

const FEATURE_CONFIG = {
  parameter_columns: [
    "ph",
    "hardness",
    "solids",
    "chloramines",
    "sulfate",
    "conductivity",
    "organic_carbon",
    "trihalomethanes",
    "turbidity",
  ],
  exclude_columns: ["potability"],
};
const pageTitles = {
  dashboard: "Главная",
  upload: "Загрузка данных",
  datasets: "Хранилище данных",
  processing: "Обработка данных",
  analytics: "Анализ данных",
  ml: "Машинное обучение",
  anomalies: "Обнаруженные аномалии",
  history: "История запусков",
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
    completed: "Завершено",
    passed: "Пройдено",
    warning: "Предупреждение",
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

async function mlRequest(path, options = {}) {
  const response = await fetch(`${API_ML}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const result = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      result.detail?.message ||
      result.detail ||
      result.message ||
      `Ошибка запроса: ${response.status}`
    );
  }

  if (result.status === "success" && "data" in result) {
    return result.data;
  }

  return result;
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
  const [batchId, setBatchId] = useState("");

  const [profile, setProfile] = useState(null);
  const [quality, setQuality] = useState(null);
  const [qualityError, setQualityError] = useState("");

  const [search, setSearch] = useState("");

  // ML
  const [models, setModels] = useState([]);
  const [modelName, setModelName] = useState("water_anomaly_detector");
  const [contamination, setContamination] = useState("0.02");

  const [mlRunId, setMlRunId] = useState("");
  const [mlRun, setMlRun] = useState(null);

  const [inferenceResult, setInferenceResult] = useState(null);
  const [anomalies, setAnomalies] = useState([]);
  const [predictions, setPredictions] = useState([]);

  const [history, setHistory] = useState([]);

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
      setBatchId(result.batch_id || "");

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
      setBatchId(profileResult.batch_id || "");

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

  // Получение списка моделей
  async function loadModels() {
    try {
      const result = await mlRequest("/models");

      setModels(Array.isArray(result) ? result : []);
    } catch (err) {
      setError(`Не удалось получить модели: ${err.message}`);
    }
  }

  // Получение данных запуска обучения
  async function checkMLRun() {
    if (!mlRunId) {
      setError("Сначала запусти обучение модели.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await mlRequest(`/runs/${mlRunId}`);

      setMlRun(result);

      setHistory((previous) => {
        const filtered = previous.filter(
          (item) => item.run_id !== result.run_id
        );

        return [result, ...filtered];
      });

      if (
        result.status === "completed" ||
        result.status === "failed"
      ) {
        await loadModels();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Обучение модели
  async function startTraining() {
    if (!selectedDataset) {
      setError("Сначала выбери набор данных.");
      return;
    }

    if (!batchId) {
      setError("Не найден Batch ID обработанного набора.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");
    setMlRun(null);

    try {
      const result = await mlRequest("/training-runs", {
        method: "POST",
        body: JSON.stringify({
          dataset_id: selectedDataset,
          batch_id: batchId,
          model_name: modelName,
          contamination: Number(contamination),
          feature_config: FEATURE_CONFIG,
        }),
      });

      const id = result.run_id || result.job_id || result.id;

      if (!id) {
        throw new Error("Сервер не вернул идентификатор запуска.");
      }

      setMlRunId(id);
      setMlRun(result);

      setHistory((previous) => [
        {
          run_id: id,
          kind: "training",
          status: result.status || "queued",
          dataset_id: selectedDataset,
          batch_id: batchId,
          model_name: modelName,
        },
        ...previous,
      ]);

      setMessage(
        `Обучение отправлено. Идентификатор: ${id}`
      );

      await loadModels();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Запуск анализа
  async function startInference() {
    if (!selectedDataset) {
      setError("Сначала выбери набор данных.");
      return;
    }

    if (!batchId) {
      setError("Не найден Batch ID обработанного набора.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");
    setInferenceResult(null);

    try {
      const result = await mlRequest("/inference", {
        method: "POST",
        body: JSON.stringify({
          dataset_id: selectedDataset,
          batch_id: batchId,
          model_name: modelName,
          allow_candidate: true,
        }),
      });

      const id = result.run_id || result.job_id || result.id;

      setInferenceResult(result);

      if (id) {
        setMlRunId(id);
      }

      setHistory((previous) => [
        {
          run_id: id || "—",
          kind: "inference",
          status: result.status || "queued",
          dataset_id: selectedDataset,
          batch_id: batchId,
          model_name: modelName,
        },
        ...previous,
      ]);

      setMessage(
        `Запрос на анализ отправлен. Идентификатор: ${id || "не получен"}`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadPredictions() {
    setLoading(true);
    setError("");

    try {
      const result = await mlRequest(
        `/predictions?dataset_id=${encodeURIComponent(selectedDataset)}&batch_id=${encodeURIComponent(batchId)}`
      );

      setPredictions(
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

  async function loadAnomalies() {
    setLoading(true);
    setError("");

    try {
      const result = await mlRequest(
        `/anomalies?dataset_id=${encodeURIComponent(selectedDataset)}&batch_id=${encodeURIComponent(batchId)}`
      );

      setAnomalies(
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
    if (activePage === "ml") {
      loadModels();
    }

    if (activePage === "anomalies" && selectedDataset && batchId) {
      loadAnomalies();
    }
  }, [activePage]);

  const filteredDatasets = datasets.filter((dataset) => {
    const text = `${dataset.name || ""} ${dataset.id || ""}`;

    return text.toLowerCase().includes(search.toLowerCase());
  });

  const successfulDatasets = datasets.filter(
    (dataset) =>
      dataset.status === "success" ||
      dataset.status === "ready"
  ).length;

  const renderDashboard = () => (
    <>
      <div className="welcome-panel">
        <div>
          <span className="eyebrow">
            ЭКОЛОГИЧЕСКИЙ МОНИТОРИНГ
          </span>

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
          description="Обработанные наборы"
          icon={CheckCircle2}
        />

        <StatCard
          title="Модели ML"
          value={models.length}
          description="Зарегистрированные модели"
          icon={BrainCircuit}
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

          <span>
            Нажми, чтобы выбрать файл на компьютере
          </span>

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

      <label className="field-label">
        Идентификатор задачи (Job ID)
      </label>

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
          ETL запускается отдельно. После его завершения
          здесь можно проверить состояние задачи.
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

      <label className="field-label">
        Выбери набор данных
      </label>

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
            setBatchId("");
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
                    <td>
                      {column.null_percent?.toFixed(2) ?? "—"}%
                    </td>
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

  // Страница машинного обучения
  const renderML = () => (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h3>Модуль машинного обучения</h3>
          <p>
            Обнаружение статистически необычных наблюдений
            с помощью Isolation Forest.
          </p>
        </div>

        <BrainCircuit size={28} />
      </div>

      <div className="notice">
        <Activity size={20} />

        <p>
          Модель ищет необычные сочетания показателей воды.
          Она не корректирует показания датчиков и не
          устанавливает безопасность воды.
        </p>
      </div>

      <label className="field-label">
        Набор данных
      </label>

      <select
        className="text-input"
        value={selectedDataset}
        onChange={(event) => {
          if (event.target.value) {
            loadProfile(event.target.value);
          } else {
            setSelectedDataset("");
            setBatchId("");
            setProfile(null);
          }
        }}
      >
        <option value="">Выбери набор данных</option>

        {datasets.map((dataset) => (
          <option key={dataset.id} value={dataset.id}>
            {dataset.name || dataset.id}
          </option>
        ))}
      </select>

      <label className="field-label">
        Batch ID обработанного набора
      </label>

      <input
        className="text-input"
        value={batchId}
        onChange={(event) => setBatchId(event.target.value)}
        placeholder="Batch ID"
      />

      <label className="field-label">
        Название модели
      </label>

      <input
        className="text-input"
        value={modelName}
        onChange={(event) => setModelName(event.target.value)}
      />

      <label className="field-label">
        Доля предполагаемых аномалий (contamination)
      </label>

      <input
        className="text-input"
        type="number"
        min="0.001"
        max="0.5"
        step="0.001"
        value={contamination}
        onChange={(event) => setContamination(event.target.value)}
      />

      <div className="result-panel">
        <h4>Используемые признаки</h4>

        <p>
          Для обучения используются девять числовых
          показателей качества воды.
        </p>

        <p>
          pH, Hardness, Solids, Chloramines, Sulfate,
          Conductivity, Organic_carbon, Trihalomethanes,
          Turbidity.
        </p>

        <p>
          <strong>Potability исключён из входных признаков.</strong>
        </p>
      </div>

      <div className="section-heading">
        <button
          className="primary-button"
          onClick={startTraining}
          disabled={
            loading ||
            !selectedDataset ||
            !batchId ||
            !modelName.trim()
          }
        >
          <BrainCircuit size={18} />
          Запустить обучение
        </button>

        <button
          className="secondary-button"
          onClick={startInference}
          disabled={
            loading ||
            !selectedDataset ||
            !batchId ||
            !modelName.trim()
          }
        >
          <Play size={18} />
          Запустить анализ
        </button>
      </div>

      {mlRunId && (
        <div className="result-panel">
          <h4>Последний запуск</h4>

          <p>
            ID: <code>{mlRunId}</code>
          </p>

          <p>
            Статус: <Status value={mlRun?.status || "queued"} />
          </p>

          <button
            className="secondary-button"
            onClick={checkMLRun}
            disabled={loading}
          >
            <RefreshCw size={18} />
            Обновить статус
          </button>

          {mlRun?.error && (
            <p className="error-text">
              {mlRun.error}
            </p>
          )}

          {mlRun?.evaluation && (
            <pre>
              {JSON.stringify(mlRun.evaluation, null, 2)}
            </pre>
          )}

          {mlRun?.summary && (
            <pre>
              {JSON.stringify(mlRun.summary, null, 2)}
            </pre>
          )}
        </div>
      )}

      {inferenceResult && (
        <div className="result-panel">
          <h4>Запрос на анализ</h4>
          <pre>
            {JSON.stringify(inferenceResult, null, 2)}
          </pre>
        </div>
      )}

      <h4>Зарегистрированные модели</h4>

      <button
        className="secondary-button"
        onClick={loadModels}
        disabled={loading}
      >
        <RefreshCw size={18} />
        Обновить список моделей
      </button>

      {models.length === 0 ? (
        <div className="empty-state">
          <BrainCircuit size={35} />
          <strong>Модели пока не зарегистрированы</strong>
          <span>
            Сначала запусти обучение и дождись его завершения.
          </span>
        </div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Модель</th>
                <th>Версия</th>
                <th>Статус</th>
              </tr>
            </thead>

            <tbody>
              {models.map((model, index) => (
                <tr key={`${model.name}-${index}`}>
                  <td>{model.name || model.model_name || "—"}</td>
                  <td>
                    {model.versions?.length
                      ? model.versions.map((v) => v.version).join(", ")
                      : "—"}
                  </td>
                  <td>
                    {model.versions?.length
                      ? model.versions.map((v) => v.status).join(", ")
                      : "Зарегистрирована"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );

  // Страница аномалий
  const renderAnomalies = () => (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h3>Обнаруженные аномалии</h3>
          <p>
            Результаты работы обученной модели.
          </p>
        </div>

        <ShieldAlert size={27} />
      </div>

      <p>
        Выбранный набор:{" "}
        <code>{selectedDataset || "не выбран"}</code>
      </p>

      <p>
        Batch ID: <code>{batchId || "не указан"}</code>
      </p>

      <button
        className="primary-button"
        onClick={loadAnomalies}
        disabled={loading || !selectedDataset || !batchId}
      >
        <RefreshCw size={18} />
        Загрузить аномалии
      </button>

      <button
        className="secondary-button"
        onClick={loadPredictions}
        disabled={loading || !selectedDataset || !batchId}
      >
        <BarChart3 size={18} />
        Все предсказания
      </button>

      {anomalies.length > 0 ? (
        <>
          <div className="stats-grid">
            <StatCard
              title="Найдено аномалий"
              value={anomalies.length}
              description="В текущей выборке"
              icon={AlertCircle}
            />
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>ID записи</th>
                  <th>Оценка аномальности</th>
                  <th>Модель</th>
                  <th>Дата</th>
                </tr>
              </thead>

              <tbody>
                {anomalies.map((item, index) => (
                  <tr key={item.prediction_id || index}>
                    <td>
                      {item.record_id || item.source_row_number || "—"}
                    </td>
                    <td>
                      {item.anomaly_score == null
                        ? "—"
                        : Number(item.anomaly_score).toFixed(5)}
                    </td>
                    <td>{item.model_name || "—"}</td>
                    <td>{formatDate(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="empty-state">
          <ShieldAlert size={35} />
          <strong>Данные об аномалиях не загружены</strong>
          <span>
            Запусти анализ, а затем обнови список.
          </span>
        </div>
      )}

      {predictions.length > 0 && (
        <>
          <h4>Все предсказания</h4>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>ID записи</th>
                  <th>Оценка</th>
                  <th>Аномалия</th>
                </tr>
              </thead>

              <tbody>
                {predictions.map((item, index) => (
                  <tr key={item.prediction_id || index}>
                    <td>
                      {item.record_id || item.source_row_number || "—"}
                    </td>
                    <td>
                      {item.anomaly_score == null
                        ? "—"
                        : Number(item.anomaly_score).toFixed(5)}
                    </td>
                    <td>
                      {item.is_anomaly ? "Да" : "Нет"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );

  // История запусков в текущей сессии интерфейса
  const renderHistory = () => (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h3>История запусков</h3>
          <p>
            Запуски обучения и анализа в текущей сессии интерфейса.
          </p>
        </div>

        <History size={27} />
      </div>

      {history.length === 0 ? (
        <div className="empty-state">
          <History size={35} />
          <strong>История пока пуста</strong>
          <span>
            Здесь появятся запуски, созданные в этом сеансе.
          </span>
        </div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>ID запуска</th>
                <th>Тип</th>
                <th>Модель</th>
                <th>Статус</th>
                <th>Действие</th>
              </tr>
            </thead>

            <tbody>
              {history.map((item, index) => (
                <tr key={item.run_id || index}>
                  <td>
                    <code>{item.run_id}</code>
                  </td>

                  <td>
                    {item.kind === "training"
                      ? "Обучение"
                      : "Анализ"}
                  </td>

                  <td>{item.model_name || "—"}</td>

                  <td>
                    <Status value={item.status} />
                  </td>

                  <td>
                    {item.run_id !== "—" && (
                      <button
                        className="table-action"
                        onClick={async () => {
                          setMlRunId(item.run_id);
                          setActivePage("ml");
                          setLoading(true);

                          try {
                            const result = await mlRequest(
                              `/runs/${item.run_id}`
                            );

                            setMlRun(result);
                          } catch (err) {
                            setError(err.message);
                          } finally {
                            setLoading(false);
                          }
                        }}
                      >
                        Открыть
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
            <span className="topbar-caption">
              РАБОЧАЯ ПАНЕЛЬ
            </span>

            <h1>{pageTitles[activePage] || "ЭКОВЕР"}</h1>
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
          {activePage === "ml" && renderML()}
          {activePage === "anomalies" && renderAnomalies()}
          {activePage === "history" && renderHistory()}
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
        <span>
          Загрузи CSV-файл, чтобы он появился здесь.
        </span>
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
                    <strong>
                      {dataset.name || "Без названия"}
                    </strong>

                    <span>{dataset.id}</span>
                  </div>
                </div>
              </td>

              <td>
                <Status value={dataset.status} />
              </td>

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
