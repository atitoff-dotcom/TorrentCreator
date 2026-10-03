// Модуль работы со скриншотами frontend/js/tab_screens.js

export class ScreensManager {
  constructor(appState) {
    this.state = appState;
    this.currentFilePath = null;
    this.candidateScreens = [];
    this.selectedScreens = [];
    this.uploadedResults = [];
    this.initElements();
    this.bindEvents();
  }

  initElements() {
    this.allGrid = document.getElementById('allScreensGrid');
    this.selectedGrid = document.getElementById('selectedScreensGrid');
    this.counterEl = document.getElementById('selectedScreensCount');
    this.uploadBtn = document.getElementById('uploadScreensBtn');
    this.addMoreBtn = document.getElementById('addMoreScreensBtn');
  }

  reset() {
    this.candidateScreens = [];
    this.selectedScreens = [];
    this.uploadedResults = [];
    this.state.selectedScreens = [];
    this.state.uploadedScreenshots = [];

    if (this.counterEl) {
      this.counterEl.textContent = '0';
    }
    if (this.selectedGrid) {
      this.selectedGrid.innerHTML = '<div style="grid-column: 1/-1; color: var(--text-muted); text-align: center; margin-top: 40px;">Кликните на кадр слева, чтобы отобрать его</div>';
    }
    if (this.allGrid) {
      this.allGrid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; margin-top: 40px; color: var(--text-muted);">⏳ Ожидание анализа видео...</div>';
    }
    if (this.uploadBtn) {
      this.uploadBtn.disabled = false;
      this.uploadBtn.textContent = 'Залить на хостинг';
    }
  }

  bindEvents() {
    if (this.addMoreBtn) {
      this.addMoreBtn.addEventListener('click', () => {
        if (!this.state.currentFilePath) {
          window.showStatus('Сначала выберите видеофайл на 1-й вкладке', 'error');
          return;
        }
        this.generateScreenshots(this.state.currentFilePath, 6);
      });
    }

    if (this.uploadBtn) {
      this.uploadBtn.addEventListener('click', () => this.uploadSelected());
    }
  }

  async generateScreenshots(filePath, count = 12) {
    if (!filePath) return;

    const isNewFile = this.currentFilePath !== filePath;
    this.currentFilePath = filePath;
    if (isNewFile) {
      this.reset();
    }

    this.allGrid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; margin-top: 40px; color: var(--text-muted);">⏳ Нарезка скриншотов через FFmpeg... Пожалуйста, подождите.</div>';
    window.showStatus('Генерация скриншотов...');

    try {
      const screens = await window.pywebview.api.make_screenshots(filePath, count);
      if (Array.isArray(screens)) {
        this.candidateScreens = screens;
        this.renderCandidates();
        
        // Автоматически отбираем первые 4 кадра для удобства (только для свежего набора)
        if (this.selectedScreens.length === 0 && screens.length >= 4) {
          this.selectedScreens = screens.slice(0, 4);
          this.renderSelected();
        } else if (this.selectedScreens.length === 0 && screens.length > 0) {
          this.selectedScreens = [...screens];
          this.renderSelected();
        }
        window.showStatus(`Нарезано кадров: ${screens.length}`, 'success');
      } else if (screens.error) {
        this.allGrid.innerHTML = `<div style="grid-column: 1/-1; color: var(--accent-red); text-align: center; margin-top: 40px;">Ошибка FFmpeg: ${screens.error}</div>`;
      }
    } catch (e) {
      window.showStatus(`Ошибка при нарезке: ${e}`, 'error');
    }
  }

  renderCandidates() {
    if (!this.candidateScreens.length) {
      this.allGrid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; margin-top: 40px; color: var(--text-muted);">Нет доступных кадров</div>';
      return;
    }

    this.allGrid.innerHTML = '';
    this.candidateScreens.forEach(item => {
      const isSelected = this.selectedScreens.some(s => s.file_path === item.file_path);
      const div = document.createElement('div');
      div.className = 'screen-thumb';
      if (isSelected) div.style.outline = '2px solid var(--accent-green)';
      
      div.innerHTML = `
        <img src="${item.data_url}" alt="Скриншот">
        <span class="screen-badge">${item.timestamp}</span>
      `;

      div.addEventListener('click', () => {
        this.toggleSelect(item);
      });

      this.allGrid.appendChild(div);
    });
  }

  toggleSelect(item) {
    const idx = this.selectedScreens.findIndex(s => s.file_path === item.file_path);
    if (idx >= 0) {
      this.selectedScreens.splice(idx, 1);
    } else {
      if (this.selectedScreens.length >= 8) {
        window.showStatus('Обычно для трекеров достаточно 4–6 скриншотов', 'info');
      }
      this.selectedScreens.push(item);
    }
    this.renderCandidates();
    this.renderSelected();
  }

  renderSelected() {
    this.counterEl.textContent = this.selectedScreens.length;
    this.state.selectedScreens = this.selectedScreens;

    if (!this.selectedScreens.length) {
      this.selectedGrid.innerHTML = '<div style="grid-column: 1/-1; color: var(--text-muted); text-align: center; margin-top: 40px;">Кликните на кадр слева, чтобы отобрать его</div>';
      return;
    }

    this.selectedGrid.innerHTML = '';
    this.selectedScreens.forEach((item, index) => {
      const div = document.createElement('div');
      div.className = 'screen-thumb';
      div.innerHTML = `
        <img src="${item.data_url}" alt="Отобранный кадр">
        <span class="screen-badge" style="background: rgba(16, 185, 129, 0.85);">${index + 1}</span>
        <button class="screen-remove-btn" title="Убрать" style="position: absolute; bottom: 4px; right: 4px; background: rgba(239, 68, 68, 0.85); border: none; color: #fff; border-radius: 3px; width: 20px; height: 20px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 11px;">✕</button>
      `;

      const removeBtn = div.querySelector('.screen-remove-btn');
      removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.selectedScreens.splice(index, 1);
        this.renderCandidates();
        this.renderSelected();
      });

      this.selectedGrid.appendChild(div);
    });
  }

  async uploadSelected() {
    if (!this.selectedScreens.length) {
      window.showStatus('Сначала отберите хотя бы один скриншот', 'error');
      return;
    }

    const paths = this.selectedScreens.map(s => s.file_path);
    const total = paths.length;
    this.uploadBtn.disabled = true;
    this.uploadBtn.textContent = 'Загрузка...';

    window.showLoader(
      'Загрузка скриншотов на Fastpic...',
      `Подготовка к загрузке 0 из ${total} (0%)`,
      0
    );
    window.showStatus(`Загрузка 0 из ${total} скриншотов на Fastpic...`);

    const results = [];
    try {
      for (let i = 0; i < total; i++) {
        const currentNum = i + 1;
        const percent = Math.round((i / total) * 100);
        window.showLoader(
          'Загрузка скриншотов на Fastpic...',
          `Загрузка кадра ${currentNum} из ${total} (${percent}%)`,
          percent
        );
        window.showStatus(`Загрузка скриншота ${currentNum} из ${total} на Fastpic...`);

        let res = null;
        if (window.pywebview.api.upload_single_screenshot) {
          res = await window.pywebview.api.upload_single_screenshot(paths[i]);
        } else {
          const bulk = await window.pywebview.api.upload_screenshots([paths[i]]);
          res = Array.isArray(bulk) && bulk.length > 0 ? bulk[0] : null;
        }

        if (res && res.success) {
          results.push(res);
        } else {
          console.warn(`Не удалось загрузить кадр ${paths[i]}:`, res);
        }

        const updatedPercent = Math.round((currentNum / total) * 100);
        window.showLoader(
          'Загрузка скриншотов на Fastpic...',
          `Загружено ${currentNum} из ${total} (${updatedPercent}%)`,
          updatedPercent
        );
      }

      if (results.length > 0) {
        this.uploadedResults = results;
        this.state.uploadedScreenshots = results;
        window.showStatus(`Успешно загружено ${results.length} из ${total} скриншотов!`, 'success');
        
        // Уведомляем Tab 3 (Релиз) об обновлении ссылок
        if (window.onScreenshotsUploaded) {
          window.onScreenshotsUploaded(results);
        }
      } else {
        window.showStatus('Ошибка при загрузке скриншотов на Fastpic', 'error');
      }
    } catch (e) {
      window.showStatus(`Ошибка загрузки: ${e}`, 'error');
    } finally {
      this.uploadBtn.disabled = false;
      this.uploadBtn.textContent = 'Залить на хостинг';
      // Небольшая задержка перед скрытием чтобы пользователь увидел 100%
      setTimeout(() => {
        window.hideLoader();
      }, 400);
    }
  }
}
