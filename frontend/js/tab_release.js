// Модуль оформления и публикации релиза frontend/js/tab_release.js
import { getReleaseFormData } from './app.js';

const LANG_OPTIONS = [
  { val: "Русский", keys: ["ru", "rus", "russian"] },
  { val: "Английский", keys: ["en", "eng", "english"] },
  { val: "Украинский", keys: ["uk", "ukr", "ukrainian"] },
  { val: "Французский", keys: ["fr", "fra", "fre", "french"] },
  { val: "Немецкий", keys: ["de", "deu", "ger", "german"] },
  { val: "Итальянский", keys: ["it", "ita", "italian"] },
  { val: "Испанский", keys: ["es", "spa", "spanish"] },
  { val: "Японский", keys: ["ja", "jpn", "japanese"] },
  { val: "Корейский", keys: ["ko", "kor", "korean"] },
  { val: "Китайский", keys: ["zh", "zho", "chi", "chinese"] },
  { val: "Польский", keys: ["pl", "pol", "polish"] },
  { val: "Другой", keys: [] }
];

const TYPE_OPTIONS = [
  { val: "dub", label: "Дублированный [ДБ]" },
  { val: "mvo", label: "Проф. многоголосый [ПМ]" },
  { val: "dvo", label: "Проф. двухголосый [ПД]" },
  { val: "pvo", label: "Проф. одноголосый [ПО]" },
  { val: "avo", label: "Авторский [АП]" },
  { val: "lmvo", label: "Любит. многоголосый [ЛМ]" },
  { val: "ldvo", label: "Любит. двухголосый [ЛД]" },
  { val: "lvo", label: "Любит. одноголосый [ЛО]" },
  { val: "original", label: "Без перевода / Оригинал [БП]" },
  { val: "ru", label: "Русский (оригинал) [РУ]" },
  { val: "tk", label: "Тифлокомментарии [ТК]" },
  { val: "dub_ts", label: "Дублированный (TS) [ДБ (TS)]" },
  { val: "funny", label: "Пародийный [(Смешной перевод)]" },
  { val: "nk", label: "Не требуется [НК]" },
  { val: "ai_dub", label: "Дубляж AI [ДБ (AI)]" },
  { val: "ai_mvo", label: "Любит. многоголосый AI [ЛМ (AI)]" },
  { val: "ai_ldvo", label: "Любит. двухголосый AI [ЛД (AI)]" },
  { val: "ai_lvo", label: "Любит. одноголосый AI [ЛО (AI)]" }
];

const SUBTITLE_TYPE_OPTIONS = [
  { val: "full", label: "Полные" },
  { val: "forced", label: "Форсированные / Надписи" },
  { val: "sdh", label: "Для слабослышащих (SDH)" },
  { val: "commentary", label: "Комментарии" }
];

export function checkIsDomestic(meta) {
  if (!meta) return false;
  const origLang = (meta.original_language || '').toLowerCase();
  if (origLang === 'ru' || origLang === 'rus' || Boolean(meta.is_russian)) {
    return true;
  }
  if (origLang && origLang !== 'ru' && origLang !== 'rus' && origLang !== 'und') {
    return false;
  }

  const countries = (meta.countries || '').toLowerCase();
  const foreignKeywords = [
    'сша', 'usa', 'великобритани', 'uk', 'франци', 'france', 'германи', 'germany',
    'япони', 'japan', 'коре', 'korea', 'италия', 'italy', 'испани', 'spain',
    'китай', 'china', 'канада', 'canada', 'австрали', 'australia', 'индия', 'india'
  ];
  const domesticKeywords = ['россия', 'ссср', 'russia', 'ussr', 'беларусь', 'belarus'];

  const hasDomestic = domesticKeywords.some(k => countries.includes(k));
  const hasForeign = foreignKeywords.some(k => countries.includes(k));

  if (hasDomestic && !hasForeign) return true;
  if (hasForeign && !hasDomestic) return false;

  const titleRu = (meta.title_ru || '').trim().toLowerCase();
  const titleOrig = (meta.title_orig || '').trim().toLowerCase();
  if (titleRu && titleOrig && titleRu === titleOrig && /[а-яёА-ЯЁ]/.test(titleRu) && !/[a-zA-Z]/.test(titleRu)) {
    return true;
  }

  return false;
}

export class ReleaseManager {
  constructor(appState) {
    this.state = appState;
    this.currentReleaseData = null;
    this.audioTracksData = [];
    this.subtitlesData = [];
    this.initElements();
    this.bindEvents();
  }

  onMetaUpdated(meta) {
    if (!meta) return;
    const isDomestic = checkIsDomestic(meta);

    // Автоматически обновляем подраздел RuTracker
    if (this.subcatSelect) {
      if (meta.is_series) {
        this.subcatSelect.value = isDomestic ? 'russian_serial_hd' : 'foreign_serial_hd';
      } else {
        this.subcatSelect.value = isDomestic ? 'russian_hd' : 'foreign_hd';
      }
    }

    // Обновляем аудиодорожки, если они уже отрисованы
    if (this.audioContainer && this.audioTracksData.length > 0) {
      const rows = this.audioContainer.querySelectorAll('.audio-track-item');
      rows.forEach((row, idx) => {
        const langSelect = row.querySelector('.track-lang-select');
        const typeSelect = row.querySelector('.track-type-select');
        const descInput = row.querySelector('.track-desc-input');
        if (!langSelect || !typeSelect || !descInput) return;

        const currentLang = langSelect.value;
        const currentType = typeSelect.value;
        const currentDesc = descInput.value.trim();

        if (currentLang === 'Русский') {
          if (isDomestic) {
            typeSelect.value = 'ru';
            if (!currentDesc || ['dub', 'mvo', 'dvo', 'pvo', 'дубляж'].includes(currentDesc.toLowerCase())) {
              descInput.value = 'Оригинал';
            }
          } else {
            // Зарубежный фильм: русский звук - это перевод!
            if (currentType === 'ru') {
              typeSelect.value = idx === 0 ? 'dub' : 'mvo';
              if (currentDesc === 'Оригинал' || currentDesc === 'Original') {
                descInput.value = '';
              }
            }
          }
        } else {
          // Иностранный язык (английский, французский и т.д.)
          if (currentType === 'ru') {
            typeSelect.value = 'original';
            descInput.value = 'Original';
          }
        }
      });
    }
  }

  initElements() {
    this.audioContainer = document.getElementById('audioTracksContainer');
    this.audioBadge = document.getElementById('audioTracksBadge');
    this.subtitlesContainer = document.getElementById('subtitlesContainer');
    this.subtitlesBadge = document.getElementById('subtitlesBadge');
    this.subcatSelect = document.getElementById('rutrackerSubcategory');
    this.infoFileInput = document.getElementById('infoFileUrl');
    this.infoFileBtn = document.getElementById('uploadInfoFileBtn');
    this.infoFileStatus = document.getElementById('infoFileStatus');
    this.publishMainBtn = document.getElementById('publishMainBtn');
    this.publishMainBtnText = document.getElementById('publishMainBtnText');
    this.currentTrackerName = document.getElementById('currentTrackerName');
    this.defaultTracker = 'kinozal';

    window.updateDefaultTracker = (tracker) => this.updateTargetTracker(tracker);
  }

  updateTargetTracker(tracker) {
    this.defaultTracker = tracker || 'kinozal';
    if (this.publishMainBtnText) {
      this.publishMainBtnText.textContent = this.defaultTracker === 'rutracker' 
        ? 'Открыть и заполнить RuTracker' 
        : 'Открыть и заполнить Кинозал';
    }
    if (this.currentTrackerName) {
      this.currentTrackerName.textContent = this.defaultTracker === 'rutracker'
        ? 'RuTracker'
        : 'Кинозал';
    }
  }

  bindEvents() {
    if (this.publishMainBtn) {
      this.publishMainBtn.addEventListener('click', () => this.handlePublishMain());
    }

    if (this.infoFileBtn) {
      this.infoFileBtn.addEventListener('click', () => this.uploadMediaInfoPaste());
    }
  }

  handlePublishMain() {
    if (this.defaultTracker === 'rutracker') {
      this.handlePublishRuTracker();
    } else {
      this.handlePublishKinozal();
    }
  }

  async uploadMediaInfoPaste() {
    if (!this.state.currentFilePath) {
      window.showStatus('Сначала выберите видеофайл', 'error');
      return;
    }
    if (this.infoFileBtn) {
      this.infoFileBtn.disabled = true;
      this.infoFileBtn.textContent = 'Загрузка...';
    }
    window.showLoader('Создание инфо-файла...', 'Заливка отчёта MediaInfo на Rentry');
    window.showStatus('Заливаем отчёт MediaInfo на Rentry...');
    try {
      const res = await window.pywebview.api.upload_mediainfo_paste();
      if (res && res.url) {
        if (this.infoFileInput) this.infoFileInput.value = res.url;
        if (this.infoFileStatus) {
          this.infoFileStatus.textContent = 'Готово ✓';
          this.infoFileStatus.style.color = 'var(--accent-green)';
        }
        window.showStatus('Инфо-файл успешно создан: ' + res.url, 'success');
      } else {
        window.showStatus('Ошибка создания инфо-файла: ' + (res?.error || 'неизвестно'), 'error');
      }
    } catch (e) {
      window.showStatus('Ошибка сети: ' + e, 'error');
    } finally {
      if (this.infoFileBtn) {
        this.infoFileBtn.disabled = false;
        this.infoFileBtn.textContent = 'Залить';
      }
      window.hideLoader();
    }
  }

  renderAudioTracks(tracks = []) {
    this.audioTracksData = tracks;
    if (!this.audioContainer) return;

    if (!tracks || tracks.length === 0) {
      if (this.audioBadge) this.audioBadge.textContent = '0 дорожек';
      this.audioContainer.innerHTML = `
        <div style="font-size: 12px; color: var(--text-muted); padding: 12px; background: var(--bg-input); border-radius: var(--radius-sm); text-align: center;">
          Выберите видеофайл для автоматического определения аудиодорожек
        </div>
      `;
      return;
    }

    if (this.audioBadge) {
      this.audioBadge.textContent = `${tracks.length} ${tracks.length === 1 ? 'дорожка' : (tracks.length < 5 ? 'дорожки' : 'дорожек')}`;
    }

    this.audioContainer.innerHTML = '';

    tracks.forEach((t, idx) => {
      const row = this.createTrackRow(t, idx);
      this.audioContainer.appendChild(row);
    });
  }

  createTrackRow(track, idx) {
    const rawLang = (track.language || 'und').toLowerCase();
    let detectedLang = 'Русский';
    for (const opt of LANG_OPTIONS) {
      if (opt.keys.includes(rawLang)) {
        detectedLang = opt.val;
        break;
      }
    }
    if (rawLang === 'und' || (!detectedLang && idx === 0)) {
      detectedLang = 'Русский';
    }

    // Проверка, является ли фильм отечественным
    const meta = (typeof getReleaseFormData === 'function' ? getReleaseFormData() : null) || this.state.metaData || {};
    const isDomestic = checkIsDomestic(meta);

    // Автоопределение типа перевода
    const title = (track.title || '').toLowerCase();
    let detectedType = 'mvo';

    if (detectedLang !== 'Русский') {
      detectedType = 'original';
    } else if (title.includes('тифло') || title.includes('audio description') || title.includes('visual description')) {
      detectedType = 'tk';
    } else if (title.includes('смешной') || title.includes('пародийн')) {
      detectedType = 'funny';
    } else if (isDomestic) {
      detectedType = 'ru'; // Для отечественного фильма русская дорожка - оригинал
    } else if (title.includes('дубл') || title.includes('dub')) {
      detectedType = 'dub';
    } else if (title.includes('двухголос') || title.includes('dvo')) {
      detectedType = 'dvo';
    } else if (title.includes('одноголос') || title.includes('pvo')) {
      detectedType = 'pvo';
    } else if (title.includes('автор') || title.includes('гаврилов') || title.includes('живов') || title.includes('володарский') || title.includes('сербин') || title.includes('михалев')) {
      detectedType = 'avo';
    } else if (title.includes('любитель') || title.includes('многоголос')) {
      detectedType = 'lmvo';
    } else if (idx === 0) {
      detectedType = 'dub'; // Для зарубежного первая русская часто дублированная
    }

    // Технический бейдж
    let srStr = '';
    if (track.sampling_rate) {
      const num = parseFloat(track.sampling_rate);
      srStr = num > 1000 ? `${(num / 1000).toFixed(1)} KHz` : `${track.sampling_rate} Hz`;
    }
    const chStr = track.channels ? `${track.channels} ch` : '';
    const brStr = track.bitrate ? `~${track.bitrate.replace('kbps', 'Kbps')}` : '';
    const techSpecs = [srStr, track.format, chStr, brStr].filter(Boolean).join(', ');

    // Начальное описание перевода/студии (с очисткой от технического мусора кодеков)
    let initDesc = (track.title || '').trim();
    if (initDesc) {
      const parenMatch = initDesc.match(/\(([^)]+)\)/);
      if (parenMatch) {
        let inside = parenMatch[1];
        inside = inside.replace(/(двухголос\w*|одноголос\w*|многоголос\w*|дублирован\w*|профессиональн\w*|любительск\w*|авторск\w*|закадров\w*|голос\w*|перевод\w*|озвучк\w*|запись с\w*)[\s,:]*/gi, '').trim();
        if (inside && !inside.match(/^(dts|ac3|aac|flac|\d+(\.\d+)?(\s*ch|\s*kbps)?)$/i)) {
          initDesc = inside.replace(/^[,.\s]+|[,.\s]+$/g, '');
        } else {
          initDesc = '';
        }
      } else if (/(dts(-hd)?|ac3|ac-3|e-ac-3|eac3|truehd|atmos|aac|flac|lpcm|mp3|\b\d+\.\d+\b|\b\d+\s*ch\b|\b\d+\s*kbps\b|\b\d+\s*k?hz\b)/i.test(initDesc)) {
        initDesc = initDesc.replace(/(dts(-hd(\s+ma)?)?|ac3|ac-3|e-ac-3|eac3|truehd|atmos|aac|flac|lpcm|mp3)[\s,]*/gi, '');
        initDesc = initDesc.replace(/\b\d+\.\d+\b[\s,]*/g, '');
        initDesc = initDesc.replace(/\b\d+\s*ch\b[\s,]*/gi, '');
        initDesc = initDesc.replace(/\b\d+\s*kbps\b[\s,]*/gi, '');
        initDesc = initDesc.replace(/\b\d+\s*k?hz\b[\s,]*/gi, '');
        initDesc = initDesc.replace(/(двухголос\w*|одноголос\w*|многоголос\w*|дублирован\w*|профессиональн\w*|любительск\w*|авторск\w*|закадров\w*)[\s,]*/gi, '');
        initDesc = initDesc.replace(/[()]/g, '').trim();
        initDesc = initDesc.replace(/^[,.\s\-–—:]+|[,.\s\-–—:]+$/g, '');
      }
    }

    const genericLower = initDesc.toLowerCase();
    if (['dub', 'дуб', 'дубляж', 'mvo', 'пм', 'dvo', 'пд', 'pvo', 'по', 'original', 'оригинал', 'rus', 'eng'].includes(genericLower)) {
      initDesc = '';
    }
    if (detectedType === 'ru') {
      initDesc = 'Оригинал';
    } else if (!initDesc && detectedType === 'original') {
      initDesc = 'Original';
    }

    const item = document.createElement('div');
    item.className = 'audio-track-item';
    item.dataset.index = idx;
    item.style.cssText = `
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      padding: 10px 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    `;

    // Генерация опций языка
    const langSelectHtml = LANG_OPTIONS.map(o => 
      `<option value="${o.val}" ${o.val === detectedLang ? 'selected' : ''}>${o.val}</option>`
    ).join('');

    // Генерация опций типа озвучки
    const typeSelectHtml = TYPE_OPTIONS.map(o => 
      `<option value="${o.val}" ${o.val === detectedType ? 'selected' : ''}>${o.label}</option>`
    ).join('');

    const trackNumStr = String(idx + 1).padStart(2, '0');

    item.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-weight: 700; color: #3b82f6;">🔊 Аудио ${trackNumStr}</span>
          <span style="font-size: 11px; color: var(--text-muted); background: var(--bg-input); padding: 2px 6px; border-radius: 4px; border: 1px solid var(--border-color);">
            ${techSpecs || 'Аудиодорожка'}
          </span>
        </div>
        <label style="display: flex; align-items: center; gap: 6px; font-size: 11px; cursor: pointer; color: var(--text-muted);">
          <input type="checkbox" class="track-enabled" checked> В релиз
        </label>
      </div>

      <div style="display: grid; grid-template-columns: 130px 170px 1fr; gap: 8px; align-items: center;">
        <div>
          <select class="form-control track-lang" style="font-size: 12px; padding: 6px 8px; height: 32px;">
            ${langSelectHtml}
          </select>
        </div>
        <div>
          <select class="form-control track-type" style="font-size: 12px; padding: 6px 8px; height: 32px;">
            ${typeSelectHtml}
          </select>
        </div>
        <div>
          <input type="text" class="form-control track-desc" value="${initDesc.replace(/"/g, '&quot;')}" placeholder="Студия / Автор (СТС, Гаврилов, Original...)" style="font-size: 12px; padding: 6px 8px; height: 32px;">
        </div>
      </div>
    `;

    // Автоматическая реакция на смену языка
    const langSelect = item.querySelector('.track-lang');
    const typeSelect = item.querySelector('.track-type');
    const descInput = item.querySelector('.track-desc');

    langSelect.addEventListener('change', () => {
      if (langSelect.value !== 'Русский') {
        typeSelect.value = 'original';
        if (!descInput.value || descInput.value === 'СТС') {
          descInput.value = 'Original';
        }
      } else {
        if (typeSelect.value === 'original') {
          typeSelect.value = 'mvo';
          if (descInput.value === 'Original') descInput.value = '';
        }
      }
    });

    return item;
  }

  renderSubtitleTracks(subtitles = []) {
    this.subtitlesData = subtitles;
    if (!this.subtitlesContainer) return;

    if (!subtitles || subtitles.length === 0) {
      if (this.subtitlesBadge) this.subtitlesBadge.textContent = '0 субтитров';
      this.subtitlesContainer.innerHTML = `
        <div style="font-size: 12px; color: var(--text-muted); padding: 12px; background: var(--bg-input); border-radius: var(--radius-sm); text-align: center;">
          В видеофайле нет встроенных субтитров
        </div>
      `;
      return;
    }

    if (this.subtitlesBadge) {
      this.subtitlesBadge.textContent = `${subtitles.length} ${subtitles.length === 1 ? 'субтитр' : (subtitles.length < 5 ? 'субтитра' : 'субтитров')}`;
    }

    this.subtitlesContainer.innerHTML = '';

    subtitles.forEach((s, idx) => {
      const row = this.createSubtitleRow(s, idx);
      this.subtitlesContainer.appendChild(row);
    });
  }

  createSubtitleRow(sub, idx) {
    const rawLang = (sub.language || 'und').toLowerCase();
    let detectedLang = 'Русский';
    for (const opt of LANG_OPTIONS) {
      if (opt.keys.includes(rawLang)) {
        detectedLang = opt.val;
        break;
      }
    }
    if (rawLang === 'und') {
      detectedLang = idx === 0 ? 'Русский' : (idx === 1 ? 'Русский' : 'Английский');
    }

    const titleLower = (sub.title || '').toLowerCase();
    let detectedType = 'full';
    if (sub.forced || titleLower.includes('forced') || titleLower.includes('надпис') || titleLower.includes('форс')) {
      detectedType = 'forced';
    } else if (titleLower.includes('sdh')) {
      detectedType = 'sdh';
    } else if (titleLower.includes('comment')) {
      detectedType = 'commentary';
    }

    let initDesc = (sub.title || '').trim();
    if (['forced', 'full', 'sdh', 'субтитры', 'subtitles', 'русский', 'английский', 'utf-8'].includes(initDesc.toLowerCase())) {
      initDesc = '';
    }

    const item = document.createElement('div');
    item.className = 'subtitle-track-item';
    item.dataset.index = idx;
    item.style.cssText = `
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      padding: 10px 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    `;

    const langSelectHtml = LANG_OPTIONS.map(o => 
      `<option value="${o.val}" ${o.val === detectedLang ? 'selected' : ''}>${o.val}</option>`
    ).join('');

    const typeSelectHtml = SUBTITLE_TYPE_OPTIONS.map(o => 
      `<option value="${o.val}" ${o.val === detectedType ? 'selected' : ''}>${o.label}</option>`
    ).join('');

    const subNumStr = String(idx + 1).padStart(2, '0');
    const formatStr = sub.format || 'SRT';

    item.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-weight: 700; color: #10b981;">💬 Субтитры ${subNumStr}</span>
          <span style="font-size: 11px; color: var(--text-muted); background: var(--bg-input); padding: 2px 6px; border-radius: 4px; border: 1px solid var(--border-color);">
            ${formatStr}${sub.forced ? ' (Forced)' : ''}
          </span>
        </div>
        <label style="display: flex; align-items: center; gap: 6px; font-size: 11px; cursor: pointer; color: var(--text-muted);">
          <input type="checkbox" class="sub-enabled" checked> В релиз
        </label>
      </div>

      <div style="display: grid; grid-template-columns: 130px 180px 1fr; gap: 8px; align-items: center;">
        <div>
          <select class="form-control sub-lang" style="font-size: 12px; padding: 6px 8px; height: 32px;">
            ${langSelectHtml}
          </select>
        </div>
        <div>
          <select class="form-control sub-type" style="font-size: 12px; padding: 6px 8px; height: 32px;">
            ${typeSelectHtml}
          </select>
        </div>
        <div>
          <input type="text" class="form-control sub-desc" value="${initDesc.replace(/"/g, '&quot;')}" placeholder="Автор / Описание (Гоблин, Нотабеноид, надписи...)" style="font-size: 12px; padding: 6px 8px; height: 32px;">
        </div>
      </div>
    `;

    return item;
  }

  getReleaseOptions() {
    const audioRows = document.querySelectorAll('.audio-track-item');
    const tracksMeta = [];

    audioRows.forEach((row) => {
      const enabled = row.querySelector('.track-enabled')?.checked ?? true;
      if (!enabled) return;

      const idx = parseInt(row.dataset.index, 10);
      const origTrack = (this.state.mediaData?.audio_tracks || [])[idx] || {};

      const lang = row.querySelector('.track-lang')?.value || 'Русский';
      const typeKey = row.querySelector('.track-type')?.value || 'mvo';
      const desc = (row.querySelector('.track-desc')?.value || '').trim();

      const typeOpt = TYPE_OPTIONS.find(o => o.val === typeKey);
      const typeLabel = typeOpt ? typeOpt.label.split('[')[0].trim() : 'Профессиональный многоголосый';

      tracksMeta.push({
        index: tracksMeta.length + 1,
        language: lang,
        translation_type_key: typeKey,
        translation_type_label: typeLabel,
        studio_or_desc: desc,
        format: origTrack.format || '',
        commercial_name: origTrack.commercial_name || '',
        channels: origTrack.channels || 2,
        bitrate: origTrack.bitrate || '',
        sampling_rate: origTrack.sampling_rate || '',
        title: desc || origTrack.title || ''
      });
    });

    // Собираем субтитры
    const subRows = document.querySelectorAll('.subtitle-track-item');
    const subsMeta = [];
    subRows.forEach((row) => {
      const enabled = row.querySelector('.sub-enabled')?.checked ?? true;
      const idx = parseInt(row.dataset.index, 10);
      const origSub = (this.state.mediaData?.subtitles || [])[idx] || {};

      const lang = row.querySelector('.sub-lang')?.value || 'Русский';
      const typeKey = row.querySelector('.sub-type')?.value || 'full';
      const desc = (row.querySelector('.sub-desc')?.value || '').trim();

      subsMeta.push({
        index: subsMeta.length + 1,
        language: lang,
        type: typeKey,
        title: desc,
        forced: typeKey === 'forced',
        enabled: enabled,
        format: origSub.format || ''
      });
    });

    const firstTrack = tracksMeta[0] || {};
    const firstRussian = tracksMeta.find(t => t.language === 'Русский') || firstTrack;

    const currentMeta = (typeof getReleaseFormData === 'function' ? getReleaseFormData() : null) || this.state.metaData || {};

    return {
      audio_tracks: tracksMeta,
      subtitle_tracks: subsMeta,
      translation_type_key: firstRussian.translation_type_key || 'mvo',
      translation_type_label: firstRussian.translation_type_label || 'Профессиональный многоголосый',
      studio: firstRussian.studio_or_desc || '',
      subcategory_key: this.subcatSelect ? this.subcatSelect.value : 'foreign_hd',
      info_file_url: (this.infoFileInput?.value || '').trim(),
      meta: currentMeta
    };
  }

  async handlePublishRuTracker() {
    if (!this.state.currentFilePath) {
      window.showStatus('Сначала выберите видеофайл', 'error');
      return;
    }

    const subcatMap = {
      "foreign_hd": 313,
      "foreign_serial_hd": 2366,
      "russian_hd": 2200,
      "russian_serial_hd": 2100,
      "animation_hd": 539
    };
    const forumId = subcatMap[this.subcatSelect?.value] || 313;

    window.showStatus('Запускаем браузер и заполняем RuTracker...', 'info');
    window.showLoader('Публикация на RuTracker...', 'Запуск браузера Chrome и заполнение темы');
    try {
      const opts = this.getReleaseOptions();
      const res = await window.pywebview.api.publish_rutracker(opts, this.state.uploadedScreenshots, forumId);
      if (res && res.error) {
        window.showStatus('Ошибка: ' + res.error, 'error');
      } else {
        if (res && res.info_file_url && this.infoFileInput) {
          this.infoFileInput.value = res.info_file_url;
          if (this.infoFileStatus) {
            this.infoFileStatus.textContent = 'Готово ✓';
            this.infoFileStatus.style.color = 'var(--accent-green)';
          }
        }
        window.showStatus(res.message || 'RuTracker успешно заполнен!', 'success');
      }
    } catch (e) {
      window.showStatus('Ошибка публикации: ' + e, 'error');
    } finally {
      window.hideLoader();
    }
  }

  async handlePublishKinozal() {
    if (!this.state.currentFilePath) {
      window.showStatus('Сначала выберите видеофайл', 'error');
      return;
    }

    try {
      const opts = this.getReleaseOptions();

      // 1. Предварительная валидация по правилам Кинозала
      if (window.pywebview && window.pywebview.api && window.pywebview.api.generate_release_data) {
        window.showStatus('Проверка релиза по правилам Кинозала...', 'info');
        const payload = await window.pywebview.api.generate_release_data(opts, this.state.uploadedScreenshots);
        const val = payload?.kinozal_validation;

        // Если обнаружены критические ошибки ручного или авто-ввода
        if (val && !val.is_valid && val.errors && val.errors.length > 0) {
          this.showKzValidationModal(val, opts);
          return;
        }
      }

      await this.executeKinozalPublish(opts);
    } catch (e) {
      window.showStatus('Ошибка публикации: ' + e, 'error');
      window.hideLoader();
    }
  }

  async executeKinozalPublish(opts) {
    window.showStatus('Запускаем браузер и заполняем поля Кинозала...', 'info');
    window.showLoader('Публикация на Кинозале...', 'Запуск браузера Chrome и заполнение полей');
    try {
      const res = await window.pywebview.api.publish_kinozal(opts, this.state.uploadedScreenshots);
      if (res && res.error) {
        window.showStatus('Ошибка: ' + res.error, 'error');
      } else {
        if (res && res.info_file_url && this.infoFileInput) {
          this.infoFileInput.value = res.info_file_url;
          if (this.infoFileStatus) {
            this.infoFileStatus.textContent = 'Готово ✓';
            this.infoFileStatus.style.color = 'var(--accent-green)';
          }
        }
        window.showStatus(res.message || 'Кинозал успешно заполнен!', 'success');
      }
    } catch (e) {
      window.showStatus('Ошибка публикации: ' + e, 'error');
    } finally {
      window.hideLoader();
    }
  }

  showKzValidationModal(val, opts) {
    const modal = document.getElementById('kzValidationModal');
    const list = document.getElementById('kzValModalList');
    const autoFixBtn = document.getElementById('kzValModalAutoFixBtn');
    const ignoreBtn = document.getElementById('kzValModalIgnoreBtn');
    const editBtn = document.getElementById('kzValModalEditBtn');
    const closeIconBtn = document.getElementById('kzValModalCloseIconBtn');

    if (!modal || !list) return;

    const allIssues = [...(val.errors || []), ...(val.warnings || [])];
    list.innerHTML = allIssues.map(item => `
      <div style="background: var(--bg-card); border-left: 3px solid ${val.errors.includes(item) ? '#ef4444' : '#f59e0b'}; padding: 8px 10px; border-radius: 3px;">
        <div style="font-weight: 600; font-size: 12.5px; color: ${val.errors.includes(item) ? '#ef4444' : '#f59e0b'}; display: flex; align-items: center; gap: 6px;">
          <span>${val.errors.includes(item) ? '❌' : '⚠️'}</span>
          <span>${item.title}</span>
        </div>
        <div style="margin-top: 3px; color: var(--text-main); font-size: 11.5px; line-height: 1.4;">
          ${item.message}
        </div>
        ${item.example_good ? `
          <div style="margin-top: 4px; font-size: 10.5px; color: var(--text-muted); font-family: monospace;">
            Правило: ${item.example_good}
          </div>
        ` : ''}
      </div>
    `).join('');

    const closeModal = () => {
      modal.classList.remove('active');
      setTimeout(() => { modal.style.display = 'none'; }, 220);
    };

    if (closeIconBtn) closeIconBtn.onclick = closeModal;
    if (editBtn) editBtn.onclick = closeModal;

    if (ignoreBtn) {
      ignoreBtn.onclick = async () => {
        closeModal();
        await this.executeKinozalPublish(opts);
      };
    }

    if (autoFixBtn) {
      autoFixBtn.onclick = async () => {
        closeModal();
        window.showStatus('Применяем автоматические исправления...', 'info');
        try {
          // Вызываем бэкенд автоисправление
          if (window.pywebview && window.pywebview.api && window.pywebview.api.auto_fix_kinozal_release) {
            const fixedOpts = await window.pywebview.api.auto_fix_kinozal_release(opts);
            await this.executeKinozalPublish(fixedOpts || opts);
          } else {
            await this.executeKinozalPublish(opts);
          }
        } catch (e) {
          await this.executeKinozalPublish(opts);
        }
      };
    }

    modal.style.display = 'flex';
    requestAnimationFrame(() => modal.classList.add('active'));
  }
}



