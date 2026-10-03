// Главный управляющий скрипт frontend/js/app.js
import { ScreensManager } from './tab_screens.js';
import { ReleaseManager } from './tab_release.js';

export const appState = {
  currentFilePath: null,
  mediaData: null,
  metaData: null,
  selectedScreens: [],
  uploadedScreenshots: []
};

let screensManager = null;
let releaseManager = null;
let loaderTimeoutId = null;
let loaderRafId = null;

window.showLoader = function(title = 'Выполняется операция...', subtitle = 'Пожалуйста, подождите', progress = null) {
  const el = document.getElementById('globalLoader');
  const textEl = document.getElementById('loaderText');
  const subtextEl = document.getElementById('loaderSubtext');
  const pCont = document.getElementById('loaderProgressContainer');
  const pBar = document.getElementById('loaderProgressBar');
  const pPerc = document.getElementById('loaderProgressPercent');

  if (textEl) textEl.textContent = title;
  if (subtextEl) subtextEl.textContent = subtitle;

  if (progress !== null && progress !== undefined && pCont && pBar) {
    const val = Math.min(100, Math.max(0, Math.round(progress)));
    pCont.style.display = 'block';
    pBar.style.width = `${val}%`;
    if (pPerc) {
      pPerc.style.display = 'block';
      pPerc.textContent = `${val}%`;
    }
  } else if (pCont) {
    pCont.style.display = 'none';
    if (pPerc) pPerc.style.display = 'none';
  }

  if (el) {
    el.style.display = 'flex';
    if (loaderRafId) cancelAnimationFrame(loaderRafId);
    loaderRafId = requestAnimationFrame(() => {
      el.classList.add('active');
    });
  }

  // Защитный авто-таймаут: оверлей гарантированно скроется через 10 секунд
  if (loaderTimeoutId) clearTimeout(loaderTimeoutId);
  loaderTimeoutId = setTimeout(() => {
    window.hideLoader();
  }, 10000);
};

window.hideLoader = function() {
  if (loaderTimeoutId) {
    clearTimeout(loaderTimeoutId);
    loaderTimeoutId = null;
  }
  if (loaderRafId) {
    cancelAnimationFrame(loaderRafId);
    loaderRafId = null;
  }
  const el = document.getElementById('globalLoader');
  if (el) {
    el.classList.remove('active');
    el.style.display = 'none';
  }
};

document.addEventListener('DOMContentLoaded', () => {
  screensManager = new ScreensManager(appState);
  releaseManager = new ReleaseManager(appState);
  initTheme();
  initTabs();
  initStatus();
  initReleaseForm();
  initFileSelection();
  initManualSearch();
  initSettings();

  document.getElementById('loaderCloseBtn')?.addEventListener('click', () => {
    window.hideLoader();
    window.showStatus('Операция отменена пользователем', 'info');
  });
});

// 1. Управление темами (Светлая / Темная)
function initTheme() {
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const themeIcon = document.getElementById('themeIcon');
  const htmlEl = document.documentElement;

  // Считываем сохраненную тему (по умолчанию dark)
  const savedTheme = localStorage.getItem('app-theme') || 'dark';
  applyTheme(savedTheme);

  themeToggleBtn.addEventListener('click', () => {
    const currentTheme = htmlEl.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
    localStorage.setItem('app-theme', newTheme);
    
    // Синхронизация с бэкендом (если pywebview готов)
    if (window.pywebview && window.pywebview.api && window.pywebview.api.set_theme) {
      window.pywebview.api.set_theme(newTheme);
    }
  });

  function applyTheme(theme) {
    htmlEl.setAttribute('data-theme', theme);
    if (theme === 'dark') {
      themeIcon.textContent = '🌙';
      themeToggleBtn.title = 'Текущая: Темная. Кликните для переключения на Светлую';
    } else {
      themeIcon.textContent = '☀️';
      themeToggleBtn.title = 'Текущая: Светлая. Кликните для переключения на Темную';
    }
  }
}

// 2. Переключение вкладок
function initTabs() {
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab');

      tabButtons.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetPane = document.getElementById(targetId);
      if (targetPane) {
        targetPane.classList.add('active');
      }

      if (targetId === 'tab-release' && releaseManager) {
        releaseManager.refreshPreview();
      }
    });
  });
}

// 3. Выбор файла или папки
function initFileSelection() {
  const selectFileBtn = document.getElementById('selectFileBtn');
  const selectFolderBtn = document.getElementById('selectFolderBtn');

  if (selectFileBtn) {
    selectFileBtn.addEventListener('click', async () => {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.select_file_dialog) {
        const selectedPath = await window.pywebview.api.select_file_dialog();
        if (selectedPath) {
          handleFileSelected(selectedPath);
        }
      } else {
        showStatus('Выбор файла доступен в оконном режиме PyWebview');
      }
    });
  }

  if (selectFolderBtn) {
    selectFolderBtn.addEventListener('click', async () => {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.select_folder_dialog) {
        const selectedFolder = await window.pywebview.api.select_folder_dialog();
        if (selectedFolder) {
          handleFileSelected(selectedFolder);
        }
      } else {
        showStatus('Выбор папки доступен в оконном режиме PyWebview');
      }
    });
  }
}

function handleFileSelected(filePath) {
  appState.currentFilePath = filePath;
  appState.selectedScreens = [];
  appState.uploadedScreenshots = [];
  if (screensManager) {
    screensManager.reset();
  }

  const infoInput = document.getElementById('infoFileUrl');
  if (infoInput) infoInput.value = '';
  const infoStatus = document.getElementById('infoFileStatus');
  if (infoStatus) {
    infoStatus.textContent = 'Загрузится автоматически';
    infoStatus.style.color = 'var(--text-muted)';
  }

  const pathDisplay = document.getElementById('selectedFilePathText');
  if (pathDisplay) {
    pathDisplay.textContent = filePath;
    pathDisplay.title = filePath;
  }

  showStatus(`Выбран: ${filePath}`);
  document.getElementById('fileBadge').textContent = 'Анализ...';
  
  if (window.pywebview && window.pywebview.api && window.pywebview.api.process_media_file) {
    window.showLoader('Анализ медиафайла...', 'FFmpeg и MediaInfo считывают аудиодорожки и субтитры');
    window.pywebview.api.process_media_file(filePath).then(result => {
      appState.mediaData = result;
      renderMediaInfo(result);
      if (releaseManager) {
        releaseManager.renderAudioTracks(result.audio_tracks || []);
        releaseManager.renderSubtitleTracks(result.subtitles || []);
      }
      if (result.clean_query) {
        document.getElementById('manualSearchInput').value = result.clean_query;
        searchMetadata(result.clean_query, result.year_guess);
      } else {
        window.hideLoader();
      }
      // Фоновый запуск нарезки скриншотов
      if (screensManager) {
        screensManager.generateScreenshots(filePath);
      }
    }).catch(err => {
      window.hideLoader();
      showStatus(`Ошибка анализа: ${err}`, 'error');
    });
  }
}

function initManualSearch() {
  const manualSearchBtn = document.getElementById('manualSearchBtn');
  const manualSearchInput = document.getElementById('manualSearchInput');
  if (manualSearchBtn && manualSearchInput) {
    const doSearch = () => {
      const q = manualSearchInput.value.trim();
      if (q) searchMetadata(q);
    };
    manualSearchBtn.addEventListener('click', doSearch);
    manualSearchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') doSearch();
    });
  }
}

function renderMediaInfo(data) {
  if (!data) return;
  document.getElementById('fileBadge').textContent = data.filename || 'Готово';
  const container = document.getElementById('mediaInfoContainer');
  
  let audioHtml = '';
  if (data.audio_tracks && data.audio_tracks.length > 0) {
    audioHtml = data.audio_tracks.map((t, idx) => `
      <div style="font-size: 11.5px; padding: 4px 8px; background: var(--bg-input); border-radius: var(--radius-sm); margin-top: 4px;">
        <strong>#${idx + 1} ${t.language.toUpperCase()}</strong>: ${t.format} ${t.channels}ch ${t.bitrate ? `(${t.bitrate})` : ''} ${t.title ? `— <em>${t.title}</em>` : ''}
      </div>
    `).join('');
  }

  container.innerHTML = `
    <div class="prop-row"><span class="prop-label">Имя файла:</span><span class="prop-value" title="${data.filename}">${data.filename || '-'}</span></div>
    <div class="prop-row"><span class="prop-label">Размер:</span><span class="prop-value">${data.file_size || '-'}</span></div>
    <div class="prop-row"><span class="prop-label">Хронометраж:</span><span class="prop-value">${data.duration || '-'}</span></div>
    <div class="prop-row"><span class="prop-label">Разрешение:</span><span class="prop-value">${data.resolution || '-'}</span></div>
    <div class="prop-row"><span class="prop-label">Видеокодек:</span><span class="prop-value">${data.video_codec || '-'}</span></div>
    <div class="prop-row"><span class="prop-label">Битрейт видео:</span><span class="prop-value">${data.video_bitrate || '-'}</span></div>
    <div style="margin-top: 10px;">
      <span class="prop-label" style="font-size: 12px; font-weight: 600;">Аудиодорожки (${data.audio_tracks ? data.audio_tracks.length : 0}):</span>
      ${audioHtml || '<div style="font-size: 12px; color: var(--text-muted);">Нет аудиодорожек</div>'}
    </div>
  `;
}

export function getReleaseFormData() {
  const current = appState.metaData || {};
  return {
    ...current,
    title_ru: (document.getElementById('metaTitleRu')?.value || '').trim(),
    title_orig: (document.getElementById('metaTitleOrig')?.value || '').trim(),
    year: (document.getElementById('metaYear')?.value || '').trim(),
    countries: (document.getElementById('metaCountry')?.value || '').trim(),
    genres: (document.getElementById('metaGenre')?.value || '').trim(),
    directors: (document.getElementById('metaDirector')?.value || '').trim(),
    actors: (document.getElementById('metaCast')?.value || '').trim(),
    poster_url: (document.getElementById('metaPoster')?.value || '').trim(),
    plot: (document.getElementById('metaPlot')?.value || '').trim(),
  };
}

export function initReleaseForm() {
  const fieldIds = [
    'metaTitleRu', 'metaTitleOrig', 'metaYear', 'metaCountry',
    'metaGenre', 'metaDirector', 'metaCast', 'metaPoster', 'metaPlot'
  ];

  const updateState = () => {
    appState.metaData = {
      ...(appState.metaData || {}),
      ...getReleaseFormData()
    };
    updatePosterPreview();
    if (releaseManager) {
      releaseManager.onMetaUpdated(appState.metaData);
    }
  };

  fieldIds.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', updateState);
    }
  });

  const posterInp = document.getElementById('metaPoster');
  if (posterInp) {
    posterInp.addEventListener('change', updatePosterPreview);
  }
}

function updatePosterPreview() {
  const url = (document.getElementById('metaPoster')?.value || '').trim();
  const thumb = document.getElementById('metaPosterThumb');
  if (!thumb) return;
  if (url) {
    thumb.src = url;
    thumb.style.display = 'block';
    thumb.onerror = () => { thumb.style.display = 'none'; };
  } else {
    thumb.style.display = 'none';
  }
}

async function searchMetadata(query, year) {
  const metaBadge = document.getElementById('metaSourceBadge');
  const dropdown = document.getElementById('searchResultsDropdown');
  if (!query) return;

  const cleanQ = query.trim();

  // Если имя файла состоит только из цифр (номер файла/диска вроде 00034, 01) - не блокируем поиск
  if (/^\d{1,5}$/.test(cleanQ)) {
    if (metaBadge) metaBadge.textContent = 'Ручной ввод';
    window.showStatus('Файл с цифровым именем. Введите название фильма вручную.', 'info');
    const titleInput = document.getElementById('metaTitleRu');
    if (titleInput && !titleInput.value) {
      titleInput.value = cleanQ;
      appState.metaData = getReleaseFormData();
    }
    return;
  }

  if (metaBadge) metaBadge.textContent = 'Поиск...';
  window.showStatus(`Ищем в Кинопоиске / TMDb: ${cleanQ}...`);
  window.showLoader('Поиск в онлайн-базах...', `Кинопоиск и TMDb: "${cleanQ}"`);

  try {
    // Ограничиваем ожидание поиска 6 секундами (защита от зависания сети)
    const searchPromise = window.pywebview.api.search_metadata(cleanQ, year);
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Таймаут ответа онлайн-баз')), 6000)
    );
    const results = await Promise.race([searchPromise, timeoutPromise]);

    if (!results || results.length === 0) {
      if (metaBadge) metaBadge.textContent = 'Ручной ввод';
      if (dropdown) dropdown.style.display = 'none';
      window.showStatus('Фильм не найден в онлайн-базах. Доступен ручной ввод.', 'info');
      
      const titleInput = document.getElementById('metaTitleRu');
      if (titleInput && !titleInput.value) {
        titleInput.value = cleanQ;
        appState.metaData = getReleaseFormData();
      }
      return;
    }

    // Если результатов несколько, отрисовываем выпадающий список вариантов
    if (dropdown) {
      dropdown.innerHTML = `
        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center; padding: 2px 4px;">
          <span>Найдено вариантов: <strong>${results.length}</strong> (Кинопоиск в приоритете)</span>
          <a href="#" id="closeSearchDropdown" style="color: var(--accent-blue); text-decoration: none; font-size: 11px;">✕ Закрыть</a>
        </div>
        <div style="display: flex; flex-direction: column; gap: 4px;">
          ${results.map((r, idx) => `
            <div class="search-match-item" data-idx="${idx}" style="display: flex; gap: 8px; align-items: center; padding: 5px 8px; border-radius: 4px; cursor: pointer; background: var(--bg-card); transition: all 0.15s ease;">
              ${r.poster_url ? `<img src="${r.poster_url}" style="width: 26px; height: 36px; object-fit: cover; border-radius: 2px; flex-shrink: 0;">` : `<div style="width: 26px; height: 36px; background: var(--bg-hover); border-radius: 2px; flex-shrink: 0;"></div>`}
              <div style="flex: 1; min-width: 0;">
                <div style="font-size: 12px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                  ${r.title_ru || r.title_orig} ${r.year ? `<span style="color: var(--text-muted); font-size: 11px;">(${r.year})</span>` : ''}
                </div>
                <div style="font-size: 11px; color: var(--text-muted); display: flex; gap: 6px; align-items: center; margin-top: 2px;">
                  <span class="badge ${r.source === 'kinopoisk' ? 'badge-orange' : 'badge-blue'}" style="font-size: 9px; padding: 1px 4px;">
                    ${r.source === 'kinopoisk' ? 'Кинопоиск' : 'TMDb'}
                  </span>
                  ${r.rating_kinopoisk ? `<span style="color: #f59e0b;">★ ${r.rating_kinopoisk}</span>` : ''}
                  ${r.title_orig && r.title_orig !== r.title_ru ? `<span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${r.title_orig}</span>` : ''}
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      `;
      dropdown.style.display = 'block';

      // Обработчик закрытия
      document.getElementById('closeSearchDropdown')?.addEventListener('click', (e) => {
        e.preventDefault();
        dropdown.style.display = 'none';
      });

      // Обработчики клика по элементам списка
      dropdown.querySelectorAll('.search-match-item').forEach(item => {
        item.addEventListener('mouseenter', () => item.style.background = 'var(--bg-hover)');
        item.addEventListener('mouseleave', () => item.style.background = 'var(--bg-card)');
        item.addEventListener('click', async () => {
          const idx = parseInt(item.getAttribute('data-idx'));
          const selected = results[idx];
          if (selected) {
            window.showLoader('Загрузка деталей...', selected.title_ru || selected.title_orig);
            window.showStatus(`Загрузка с ${selected.source === 'kinopoisk' ? 'Кинопоиска' : 'TMDb'}: ${selected.title_ru}...`);
            try {
              const details = await window.pywebview.api.get_metadata_details(selected.source, selected.id, selected.is_series);
              if (details) {
                renderMetaDetails(details);
                if (metaBadge) metaBadge.textContent = selected.source === 'kinopoisk' ? 'КИНОПОИСК' : 'TMDB';
                window.showStatus(`Загружено: ${details.title_ru || query} (${selected.source === 'kinopoisk' ? 'Кинопоиск' : 'TMDb'})`, 'success');
                dropdown.style.display = 'none';
              }
            } catch (err) {
              window.showStatus(`Ошибка загрузки: ${err}`, 'error');
            } finally {
              window.hideLoader();
            }
          }
        });
      });
    }

    // По умолчанию сразу подгружаем первый (наиболее релевантный) результат Кинопоиска
    const first = results[0];
    const details = await window.pywebview.api.get_metadata_details(first.source, first.id, first.is_series);
    if (details) {
      renderMetaDetails(details);
      if (metaBadge) metaBadge.textContent = first.source === 'kinopoisk' ? 'КИНОПОИСК' : 'TMDB';
      window.showStatus(`Найдено: ${details.title_ru || query} (${first.source === 'kinopoisk' ? 'Кинопоиск' : 'TMDb'})`, 'success');
    }
  } catch (err) {
    if (metaBadge) metaBadge.textContent = 'Ручной ввод';
    window.showStatus(`Ошибка поиска: ${err}. Доступен ручной ввод.`, 'error');
  } finally {
    window.hideLoader();
  }
}

function renderMetaDetails(m) {
  if (!m) return;
  appState.metaData = m;

  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val || '';
  };

  setVal('metaTitleRu', m.title_ru);
  setVal('metaTitleOrig', m.title_orig);
  setVal('metaYear', m.year);
  setVal('metaCountry', m.countries);
  setVal('metaGenre', m.genres);
  setVal('metaDirector', m.directors);
  setVal('metaCast', m.actors);
  setVal('metaPoster', m.poster_url);
  setVal('metaPlot', m.plot);

  updatePosterPreview();
  appState.metaData = {
    ...m,
    ...getReleaseFormData()
  };

  if (releaseManager) {
    releaseManager.onMetaUpdated(appState.metaData);
  }
}

// 4. Инициализация статусбара
function initStatus() {
  window.showStatus = function(message, type = 'info') {
    const el = document.getElementById('statusMessage');
    if (el) {
      el.textContent = message;
      if (type === 'error') {
        el.style.color = 'var(--accent-red)';
      } else if (type === 'success') {
        el.style.color = 'var(--accent-green)';
      } else {
        el.style.color = 'var(--text-muted)';
      }
    }
  };
}

// 5. Настройки и FFmpeg
function initSettings() {
  const saveBtn = document.getElementById('saveSettingsBtn');
  const browseFfmpegBtn = document.getElementById('browseFfmpegBtn');
  const downloadFfmpegBtn = document.getElementById('downloadFfmpegBtn');
  const ffmpegBadge = document.getElementById('ffmpegStatusBadge');
  const ffmpegPathInput = document.getElementById('settingFfmpegPath');
  const ffmpegVerText = document.getElementById('ffmpegVersionText');
  const defaultTrackerSelect = document.getElementById('settingDefaultTracker');

  const updateFfmpegUI = (status) => {
    if (!status) return;
    if (status.found) {
      if (ffmpegBadge) {
        if (status.is_outdated) {
          ffmpegBadge.className = 'badge badge-yellow';
          ffmpegBadge.textContent = 'Устаревший';
        } else {
          ffmpegBadge.className = 'badge badge-green';
          ffmpegBadge.textContent = 'Активен';
        }
      }
      if (ffmpegPathInput) ffmpegPathInput.value = status.path || '';
      if (ffmpegVerText) {
        ffmpegVerText.textContent = `v${status.version || 'актуальная'}` + (status.is_outdated ? ' (рекомендуется 5.0+)' : '');
        ffmpegVerText.style.color = status.is_outdated ? 'var(--accent-yellow)' : 'var(--accent-green)';
      }
    } else {
      if (ffmpegBadge) {
        ffmpegBadge.className = 'badge badge-red';
        ffmpegBadge.textContent = 'Не найден';
      }
      if (ffmpegPathInput) ffmpegPathInput.value = '';
      if (ffmpegVerText) {
        ffmpegVerText.textContent = 'Утилита не обнаружена';
        ffmpegVerText.style.color = 'var(--accent-red)';
      }
    }
  };

  // Загрузка настроек из бэкенда
  const loadSettings = async () => {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_config) {
      const cfg = await window.pywebview.api.get_config();
      if (cfg) {
        if (cfg.kinopoisk_api_key) document.getElementById('settingKinopoiskKey').value = cfg.kinopoisk_api_key;
        if (cfg.tmdb_api_key) document.getElementById('settingTmdbKey').value = cfg.tmdb_api_key;
        if (cfg.image_host) document.getElementById('settingImageHost').value = cfg.image_host;
        if (cfg.default_tracker && defaultTrackerSelect) {
          defaultTrackerSelect.value = cfg.default_tracker;
          if (window.updateDefaultTracker) window.updateDefaultTracker(cfg.default_tracker);
        }
      }
    }

    if (window.pywebview && window.pywebview.api && window.pywebview.api.check_ffmpeg_status) {
      const status = await window.pywebview.api.check_ffmpeg_status();
      updateFfmpegUI(status);
      checkFfmpegStartup(status);
    }
  };

  // Слушаем готовность pywebview
  window.addEventListener('pywebviewready', loadSettings);
  setTimeout(loadSettings, 500);

  if (defaultTrackerSelect) {
    defaultTrackerSelect.addEventListener('change', () => {
      if (window.updateDefaultTracker) window.updateDefaultTracker(defaultTrackerSelect.value);
    });
  }

  if (browseFfmpegBtn) {
    browseFfmpegBtn.addEventListener('click', async () => {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.select_ffmpeg_file) {
        const res = await window.pywebview.api.select_ffmpeg_file();
        if (res && res.found) {
          updateFfmpegUI(res);
          showStatus(`FFmpeg настроен: ${res.version}`, 'success');
        } else if (!res.cancelled) {
          showStatus('Выбран некорректный файл FFmpeg', 'error');
        }
      }
    });
  }

  if (downloadFfmpegBtn) {
    downloadFfmpegBtn.addEventListener('click', () => triggerFfmpegDownload(updateFfmpegUI));
  }

  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const config = {
        kinopoisk_api_key: document.getElementById('settingKinopoiskKey').value,
        tmdb_api_key: document.getElementById('settingTmdbKey').value,
        image_host: document.getElementById('settingImageHost').value,
        default_tracker: defaultTrackerSelect ? defaultTrackerSelect.value : 'kinozal'
      };

      if (window.updateDefaultTracker) window.updateDefaultTracker(config.default_tracker);

      if (window.pywebview && window.pywebview.api && window.pywebview.api.save_config) {
        await window.pywebview.api.save_config(config);
        showStatus('Настройки успешно сохранены!', 'success');
      } else {
        showStatus('Настройки сохранены локально', 'success');
      }
    });
  }

  // Обработчик ссылок-подсказок для получения API ключей
  document.querySelectorAll('.ext-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const url = link.getAttribute('data-url');
      if (url && window.pywebview && window.pywebview.api && window.pywebview.api.open_browser_url) {
        window.pywebview.api.open_browser_url(url);
      }
    });
  });

  // Кнопка копирования безопасного описания для TMDb
  const copyTmdbBtn = document.getElementById('copyTmdbDescBtn');
  if (copyTmdbBtn) {
    copyTmdbBtn.addEventListener('click', async () => {
      const text = "A personal desktop application for cataloging and organizing my home video archive and family media collection. It reads local video files and displays movie posters, genres, directors, and cast information for personal offline viewing and library management.";
      await navigator.clipboard.writeText(text);
      showStatus('Безопасное описание для TMDb скопировано в буфер обмена!', 'success');
      alert('Текст описания скопирован в буфер обмена!\n\nВставьте его (Ctrl+V) в поле "Application Summary" в форме регистрации ключа на TMDb.');
    });
  }
}

// Проверка FFmpeg при старте и модальное окно
function checkFfmpegStartup(status) {
  if (!status || (status.found && !status.is_outdated)) {
    return; // Всё в порядке
  }

  const modal = document.getElementById('ffmpegModal');
  const title = document.getElementById('ffmpegModalTitle');
  const subtitle = document.getElementById('ffmpegModalSubtitle');
  const desc = document.getElementById('ffmpegModalDesc');
  const dlBtn = document.getElementById('modalDownloadFfmpegBtn');
  const browseBtn = document.getElementById('modalBrowseFfmpegBtn');
  const ignoreBtn = document.getElementById('modalIgnoreFfmpegBtn');

  if (!modal) return;

  if (status.found && status.is_outdated) {
    if (title) title.textContent = 'Обнаружен устаревший FFmpeg';
    if (subtitle) subtitle.textContent = `Текущая версия: ${status.version}`;
    if (desc) desc.textContent = 'У вас установлена старая версия FFmpeg (< 5.0). Для стабильной работы с современным видео (HEVC, AV1, 10-бит) и быстрой нарезки кадров рекомендуется обновиться.';
    if (dlBtn) dlBtn.textContent = '⬇️ Обновить FFmpeg автоматически';
  } else {
    if (title) title.textContent = 'Требуется утилита FFmpeg';
    if (subtitle) subtitle.textContent = 'Необходима для анализа видео и нарезки кадров';
    if (desc) desc.textContent = 'FFmpeg не обнаружен в вашей системе. Для автоматической работы вы можете скачать его в один клик прямо в папку программы, либо указать путь вручную.';
    if (dlBtn) dlBtn.textContent = '⬇️ Скачать FFmpeg автоматически';
  }

  modal.style.display = 'flex';
  requestAnimationFrame(() => modal.classList.add('active'));

  if (ignoreBtn) {
    ignoreBtn.onclick = () => {
      modal.classList.remove('active');
      setTimeout(() => modal.style.display = 'none', 250);
    };
  }

  if (browseBtn) {
    browseBtn.onclick = async () => {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.select_ffmpeg_file) {
        const res = await window.pywebview.api.select_ffmpeg_file();
        if (res && res.found) {
          modal.classList.remove('active');
          setTimeout(() => modal.style.display = 'none', 250);
          showStatus(`FFmpeg настроен: ${res.version}`, 'success');
          const badge = document.getElementById('ffmpegStatusBadge');
          if (badge) {
            badge.className = 'badge badge-green';
            badge.textContent = 'Активен';
          }
        }
      }
    };
  }

  if (dlBtn) {
    dlBtn.onclick = async () => {
      modal.classList.remove('active');
      setTimeout(() => modal.style.display = 'none', 250);
      triggerFfmpegDownload();
    };
  }
}

async function triggerFfmpegDownload(onCompleteCallback = null) {
  window.showLoader(
    'Загрузка FFmpeg...',
    'Скачивание официальной статической сборки...',
    15
  );
  window.showStatus('Скачивание и настройка FFmpeg...');

  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.download_ffmpeg) {
      window.showLoader('Загрузка FFmpeg...', 'Распаковка и проверка бинарного файла...', 85);
      const res = await window.pywebview.api.download_ffmpeg();
      if (res && res.success) {
        window.showLoader('Загрузка FFmpeg...', 'Готово! FFmpeg успешно настроен', 100);
        window.showStatus(`FFmpeg успешно установлен: ${res.version}!`, 'success');
        if (onCompleteCallback) {
          onCompleteCallback({
            found: true,
            is_outdated: false,
            path: res.path,
            version: res.version
          });
        }
      } else {
        window.showStatus('Ошибка скачивания FFmpeg: ' + (res.error || 'неизвестно'), 'error');
      }
    }
  } catch (e) {
    window.showStatus('Ошибка загрузки: ' + e, 'error');
  } finally {
    setTimeout(() => {
      window.hideLoader();
    }, 600);
  }
}

  // Ручной поиск фильма/сериала
  const searchBtn = document.getElementById('manualSearchBtn');
  const searchInput = document.getElementById('manualSearchInput');
  if (searchBtn && searchInput) {
    const triggerSearch = () => {
      const q = searchInput.value.trim();
      if (q) {
        searchMetadata(q);
      }
    };
    searchBtn.addEventListener('click', triggerSearch);
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') triggerSearch();
    });
  }
}
