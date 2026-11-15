
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
  AlertTriangle,
  History,
  Play,
  BarChart3,
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
  ml: "Машинное обучение",
  anomalies: "Обнаруженные аномалии",
  history: "История запусков",
};

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString("ru-RU");
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
    candidate: "Кандидат",
    staging: "Тестовая",
    production: "Рабочая",
    archived: "Архивная",
    unknown: "Неизвестно",
  };

  return (
    <span className={`status status-${status}`}>
      {labels[status] || status}
    </span>
  );
}

function getItems(result) {
  if (Array.isArray(result)) return result;
  if (Array.isArray(result?.items)) return result.items;
  if (Array.isArray(result?.models)) return result.models;
  if (Array.isArray(result?.runs)) return result.runs;
  if (Array.isArray(result?.predictions)) return result.predictions;
  if (Array.isArray(result?.anomalies)) return result.anomalies;
  return [];
}

function getRunId(result) {
  return result?.job_id || result?.run_id || result?.id || "";
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

  // Машинное обучение
  const [models, setModels] = useState([]);
  const [modelName, setModelName] = useState("water_anomaly_detector");
  const [contamination, setContamination] = useState("0.02");
  const [excludeColumns, setExcludeColumns] = useState("");

  const [mlRunId, setMlRunId] = useState("");
  const [mlRun, setMlRun] = useState(null);
  const [inferenceResult, setInferenceResult] = useState(null);

  // Аномалии и предсказания
  const [anomalies, setAnomalies] = useState([]);
  const [predictions, setPredictions] = useState([]);

  // История
  const [history, setHistory] = useState([]);

  async function loadDatasets() {
    setLoading(true);
    setError("");

    try {
      const result = await api.getDatasets();

      setDatasets(
        Array.isArray(result)
          ? result
          : result?.items || []
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

      console.log("PROFILE RESULT:", profileResult);
      console.log("PROFILE COLUMNS:", profileResult?.columns);

      setProfile(profileResult);

      const currentBatchId =
        profileResult?.batch_id ||
        profileResult?.latest_batch_id ||
        "";

      if (currentBatchId) {
        setBatchId(currentBatchId);
      }

      try {
        if (currentBatchId) {
          const qualityResult = await api.getQuality(
            datasetId,
            currentBatchId
          );

          setQuality(qualityResult);
        } else {
          setQualityError(
            "В профиле не найден batch_id обработанного набора."
          );
        }
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

  // -----------------------------
  // Машинное обучение
  // -----------------------------

  async function loadModels() {
    try {
      const result = await api.getModels();
      setModels(getItems(result));
    } catch (err) {
      setError(`Не удалось загрузить модели: ${err.message}`);
    }
  }

  async function loadHistory() {
    try {
      const result = await api.getMLRuns({ limit: 100 });
      setHistory(getItems(result));
    } catch (err) {
      setError(`Не удалось загрузить историю: ${err.message}`);
    }
  }

  async function loadPredictions() {
    if (!selectedDataset || !batchId) {
      setPredictions([]);
      return;
    }

    try {
      const result = await api.getPredictions({
        dataset_id: selectedDataset,
        batch_id: batchId,
        limit: 100,
      });

      setPredictions(getItems(result));
    } catch (err) {
      setError(`Не удалось загрузить предсказания: ${err.message}`);
    }
  }

  async function loadAnomalies() {
    if (!selectedDataset || !batchId) {
      setAnomalies([]);
      return;
    }

    try {
      const result = await api.getAnomalies({
        dataset_id: selectedDataset,
        batch_id: batchId,
        limit: 100,
      });

      setAnomalies(getItems(result));
    } catch (err) {
      setError(`Не удалось загрузить аномалии: ${err.message}`);
    }
  }

  async function checkMLRun() {
    if (!mlRunId) {
      setError("Сначала запусти обучение или инференс.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await api.getMLRun(mlRunId);

      setMlRun(result);

      const status = String(result?.status || "").toLowerCase();

      if (status === "completed" || status === "success") {
        setMessage("Задача успешно завершена.");
        await loadModels();
        await loadHistory();
      } else if (status === "failed") {
        setError(
          result?.error ||
          result?.error_message ||
          "Во время выполнения ML-задачи произошла ошибка."
        );

        await loadHistory();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function startTraining() {
    if (!selectedDataset) {
      setError("Выбери набор данных для обучения.");
      return;
    }

    if (!batchId) {
      setError(
        "Не найден batch_id. Сначала обработай набор данных и получи его профиль."
      );
      return;
    }

    if (!modelName.trim()) {
      setError("Укажи название модели.");
      return;
    }

    const contaminationValue = Number(contamination);

    if (
      !Number.isFinite(contaminationValue) ||
      contaminationValue <= 0 ||
      contaminationValue > 0.5
    ) {
      setError("Contamination должен быть больше 0 и не больше 0.5.");
      return;
    }

    const excluded = excludeColumns
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

    setLoading(true);
    setError("");
    setMessage("");
    setMlRun(null);
    setInferenceResult(null);

    try {
      const result = await api.startTraining({
        dataset_id: selectedDataset,
        batch_id: batchId,
        model_name: modelName.trim(),
        contamination: contaminationValue,
        feature_config: {
          exclude_columns: excluded,
        },
      });

      const newRunId = getRunId(result);

      setMlRunId(newRunId);
      setMlRun({
        ...result,
        status: result?.status || "queued",
      });

      setMessage(
        newRunId
          ? `Обучение поставлено в очередь. ID задачи: ${newRunId}`
          : "Запрос на обучение отправлен."
      );

      await loadHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function startInference() {
    if (!selectedDataset) {
      setError("Выбери набор данных для поиска аномалий.");
      return;
    }

    if (!batchId) {
      setError("Не найден batch_id обработанного набора.");
      return;
    }

    if (!modelName.trim()) {
      setError("Укажи название модели.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");
    setInferenceResult(null);

    try {
      const result = await api.startInference({
        dataset_id: selectedDataset,
        batch_id: batchId,
        model_name: modelName.trim(),
        allow_candidate: true,
      });

      const newRunId = getRunId(result);

      setMlRunId(newRunId);
      setMlRun({
        ...result,
        status: result?.status || "queued",
      });

      setMessage(
        newRunId
          ? `Поиск аномалий поставлен в очередь. ID задачи: ${newRunId}`
          : "Запрос на поиск аномалий отправлен."
      );

      await loadHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function refreshMLData() {
    setLoading(true);
    setError("");

    try {
      await Promise.all([
        loadModels(),
        loadHistory(),
      ]);

      if (selectedDataset && batchId) {
        await Promise.all([
          loadPredictions(),
          loadAnomalies(),
        ]);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (activePage === "ml") {
      loadModels();
    }

    if (activePage === "history") {
      loadHistory();
    }

    if (activePage === "anomalies") {
      loadAnomalies();
      loadPredictions();
    }
  }, [activePage]);

  // -----------------------------
  // Главная
  // -----------------------------

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

  // -----------------------------
  // Загрузка
  // -----------------------------

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
          <p>
            Статус: <Status value={uploadResult.status} />
          </p>
          <p>
            Dataset ID: <code>{uploadResult.dataset_id}</code>
          </p>
          <p>
            Version ID: <code>{uploadResult.version_id}</code>
          </p>
          <p>
            Job ID: <code>{uploadResult.job_id}</code>
          </p>
          <p>
            Batch ID: <code>{uploadResult.batch_id || "—"}</code>
          </p>
          <p>{uploadResult.message}</p>
        </div>
      )}
    </section>
  );

  // -----------------------------
  // Хранилище
  // -----------------------------

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

  // -----------------------------
  // Обработка
  // -----------------------------

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
          <p>
            ID задачи: <code>{job.id}</code>
          </p>
          <p>
            Статус: <Status value={job.status} />
          </p>

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

  // -----------------------------
  // Аналитика
  // -----------------------------

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
                {qualityError ||
                  "Отчёт качества пока недоступен."}
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );

  // -----------------------------
  // Машинное обучение
  // -----------------------------

  const renderML = () => (
    <>
      <section className="content-card">
        <div className="section-heading">
          <div>
            <h3>Обучение модели обнаружения аномалий</h3>
            <p>
              Обучение Isolation Forest на обработанных данных.
            </p>
          </div>

          <BrainCircuit size={27} />
        </div>

        <label className="field-label">
          Набор данных
        </label>

        <select
          className="text-input"
          value={selectedDataset}
          onChange={(event) => {
            const value = event.target.value;

            setSelectedDataset(value);
            setBatchId("");
            setProfile(null);
            setQuality(null);

            if (value) {
              loadProfile(value);
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
          placeholder="Например, water_anomaly_detector"
        />

        <label className="field-label">
          Contamination — ожидаемая доля аномалий
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

        <label className="field-label">
          Столбцы, которые нужно исключить из обучения
        </label>

        <input
          className="text-input"
          value={excludeColumns}
          onChange={(event) => setExcludeColumns(event.target.value)}
          placeholder="Например: id, potability, record_id"
        />

        <div className="notice">
          <BrainCircuit size={20} />
          <p>
            Если список исключаемых столбцов оставить пустым,
            система автоматически выберет подходящие числовые
            признаки. Названия столбцов вводятся через запятую.
            Для обучения требуется не менее 20 пригодных записей.
          </p>
        </div>

        <div className="button-row">
          <button
            className="primary-button"
            onClick={startTraining}
            disabled={loading || !selectedDataset || !batchId}
          >
            <Play size={18} />
            Запустить обучение
          </button>

          <button
            className="secondary-button"
            onClick={startInference}
            disabled={loading || !selectedDataset || !batchId}
          >
            <Activity size={18} />
            Найти аномалии
          </button>
        </div>
      </section>

      <section className="content-card">
        <div className="section-heading">
          <div>
            <h3>Последний запуск</h3>
            <p>Состояние задачи обучения или инференса.</p>
          </div>

          <button
            className="icon-button"
            onClick={checkMLRun}
            disabled={loading || !mlRunId}
            title="Проверить состояние"
          >
            <RefreshCw size={19} />
          </button>
        </div>

        {mlRunId ? (
          <div className="result-panel">
            <p>
              ID запуска: <code>{mlRunId}</code>
            </p>

            <p>
              Статус:{" "}
              <Status value={mlRun?.status} />
            </p>

            {mlRun?.kind && (
              <p>Тип: {mlRun.kind}</p>
            )}

            {mlRun?.model_name && (
              <p>Модель: {mlRun.model_name}</p>
            )}

            {mlRun?.error && (
              <p className="error-text">{mlRun.error}</p>
            )}

            {mlRun?.error_message && (
              <p className="error-text">
                {mlRun.error_message}
              </p>
            )}

            {mlRun?.evaluation && (
              <>
                <h4>Результаты оценки</h4>
                <pre className="json-result">
                  {JSON.stringify(mlRun.evaluation, null, 2)}
                </pre>
              </>
            )}

            {inferenceResult && (
              <>
                <h4>Результат инференса</h4>
                <pre className="json-result">
                  {JSON.stringify(inferenceResult, null, 2)}
                </pre>
              </>
            )}
          </div>
        ) : (
          <div className="empty-state">
            <Clock3 size={34} />
            <strong>Запусков пока нет</strong>
            <span>
              После запуска обучения здесь появится информация о задаче.
            </span>
          </div>
        )}
      </section>

      <section className="content-card">
        <div className="section-heading">
          <div>
            <h3>Зарегистрированные модели</h3>
            <p>Модели и доступные версии в реестре.</p>
          </div>

          <button
            className="icon-button"
            onClick={loadModels}
            title="Обновить модели"
          >
            <RefreshCw size={19} />
          </button>
        </div>

        {models.length ? (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Название</th>
                  <th>Последняя версия</th>
                  <th>Рабочая версия</th>
                  <th>Количество версий</th>
                </tr>
              </thead>

              <tbody>
                {models.map((model, index) => (
                  <tr key={model.model_name || index}>
                    <td>
                      <strong>{model.model_name || "—"}</strong>
                    </td>
                    <td>{model.latest_version || "—"}</td>
                    <td>{model.production_version || "Не назначена"}</td>
                    <td>{model.versions?.length || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <BrainCircuit size={34} />
            <strong>Модели пока не зарегистрированы</strong>
            <span>
              Сначала запусти обучение на обработанном наборе.
            </span>
          </div>
        )}
      </section>
    </>
  );

  // -----------------------------
  // Обнаруженные аномалии
  // -----------------------------

  const renderAnomalies = () => (
    <>
      <section className="content-card">
        <div className="section-heading">
          <div>
            <h3>Обнаруженные аномалии</h3>
            <p>
              Результаты работы модели на выбранном наборе данных.
            </p>
          </div>

          <AlertTriangle size={26} />
        </div>

        <label className="field-label">
          Набор данных
        </label>

        <select
          className="text-input"
          value={selectedDataset}
          onChange={(event) => {
            const value = event.target.value;

            setSelectedDataset(value);
            setBatchId("");

            if (value) {
              loadProfile(value);
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

        <label className="field-label">
          Batch ID
        </label>

        <input
          className="text-input"
          value={batchId}
          onChange={(event) => setBatchId(event.target.value)}
          placeholder="Batch ID"
        />

        <button
          className="primary-button"
          onClick={async () => {
            setLoading(true);
            setError("");

            try {
              await Promise.all([
                loadAnomalies(),
                loadPredictions(),
              ]);
            } finally {
              setLoading(false);
            }
          }}
          disabled={loading || !selectedDataset || !batchId}
        >
          <Search size={18} />
          Загрузить результаты
        </button>
      </section>

      <section className="content-card">
        <div className="section-heading">
          <div>
            <h3>Сводка</h3>
            <p>Количество результатов текущего набора.</p>
          </div>

          <BarChart3 size={25} />
        </div>

        <div className="stats-grid">
          <StatCard
            title="Проверено записей"
            value={predictions.length}
            description="Получено предсказаний"
            icon={Database}
          />

          <StatCard
            title="Аномалии"
            value={anomalies.length}
            description="Записи, отмеченные моделью"
            icon={AlertTriangle}
          />

          <StatCard
            title="Обычные записи"
            value={Math.max(predictions.length - anomalies.length, 0)}
            description="Без отметки об аномалии"
            icon={CheckCircle2}
          />
        </div>

        {anomalies.length ? (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Запись</th>
                  <th>Строка источника</th>
                  <th>Станция</th>
                  <th>Модель</th>
                  <th>Версия</th>
                  <th>Оценка аномалии</th>
                  <th>Дата</th>
                </tr>
              </thead>

              <tbody>
                {anomalies.map((item, index) => (
                  <tr key={item.prediction_id || index}>
                    <td>{item.record_id || "—"}</td>
                    <td>{item.source_row_number ?? "—"}</td>
                    <td>{item.station_id || "—"}</td>
                    <td>{item.model_name || "—"}</td>
                    <td>{item.model_version || "—"}</td>
                    <td>
                      {item.anomaly_score == null
                        ? "—"
                        : Number(item.anomaly_score).toFixed(5)}
                    </td>
                    <td>{formatDate(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <AlertTriangle size={34} />
            <strong>Аномалии не найдены</strong>
            <span>
              Выбери обработанный набор и загрузи результаты модели.
            </span>
          </div>
        )}
      </section>
    </>
  );

  // -----------------------------
  // История запусков
  // -----------------------------

  const renderHistory = () => (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h3>История запусков ML</h3>
          <p>
            Сохранённые результаты обучения и поиска аномалий.
          </p>
        </div>

        <button
          className="icon-button"
          onClick={loadHistory}
          title="Обновить историю"
        >
          <RefreshCw size={19} />
        </button>
      </div>

      {history.length ? (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>ID запуска</th>
                <th>Тип</th>
                <th>Модель</th>
                <th>Набор данных</th>
                <th>Статус</th>
                <th>Начало</th>
              </tr>
            </thead>

            <tbody>
              {history.map((item, index) => (
                <tr key={item.run_id || item.id || index}>
                  <td>
                    <code>{item.run_id || item.id || "—"}</code>
                  </td>
                  <td>{item.kind || item.type || "—"}</td>
                  <td>{item.model_name || "—"}</td>
                  <td>{item.dataset_id || "—"}</td>
                  <td>
                    <Status value={item.status} />
                  </td>
                  <td>
                    {formatDate(
                      item.started_at ||
                      item.created_at ||
                      item.finished_at
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <History size={34} />
          <strong>История пока пуста</strong>
          <span>
            Здесь появятся сохранённые запуски после обучения модели
            или выполнения инференса.
          </span>
        </div>
      )}
    </section>
  );

  // -----------------------------
  // Основной интерфейс
  // -----------------------------

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
