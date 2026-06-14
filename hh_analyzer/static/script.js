/**
 * Main JavaScript for HH.ru Analytics
 */

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('calculator-form');
    const resultsContainer = document.getElementById('results');
    const errorMessage = document.getElementById('error-message');
    const calculateBtn = document.getElementById('calculate-btn');
    const copyLinkBtn = document.getElementById('copy-link-btn');
    const debugToggle = document.getElementById('debug-toggle');
    const debugContainer = document.getElementById('query-debug');
    
    initSearchableSelects();
    initKeywordSuggest();
    initCollapsibleSections();
    applyPrefillFromServer();
    applyPrefillFromUrl();
    
    if (debugToggle) {
        debugToggle.addEventListener('click', function() {
            document.getElementById('debug-content').classList.toggle('active');
            debugToggle.classList.toggle('active');
        });
    }

    if (copyLinkBtn) {
        copyLinkBtn.addEventListener('click', async function() {
            const url = buildShareUrl();
            try {
                await navigator.clipboard.writeText(url);
                copyLinkBtn.textContent = 'Ссылка скопирована';
                setTimeout(() => { copyLinkBtn.textContent = 'Скопировать ссылку'; }, 2000);
            } catch (error) {
                window.prompt('Скопируйте ссылку:', url);
            }
        });
    }
    
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            setLoading(true);
            hideResults();
            hideError();
            
            const formData = new FormData(form);
            
            try {
                const response = await fetch('/api/calculate', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showResults(data);
                    updateShareUrl();
                } else {
                    showError(data.error || 'Произошла ошибка при расчете');
                }
            } catch (error) {
                showError('Ошибка соединения с сервером');
                console.error('Error:', error);
            } finally {
                setLoading(false);
            }
        });
    }
    
    function initCollapsibleSections() {
        const collapsibles = document.querySelectorAll('.collapsible');
        
        collapsibles.forEach(section => {
            const header = section.querySelector('.collapsible-header');
            
            header.addEventListener('click', function() {
                section.classList.toggle('active');
            });
        });
    }
    
    initResumeTextTriad();
    
    function initResumeTextTriad() {
        const textField = document.getElementById('resume_text_field');
        const textPeriod = document.getElementById('resume_text_period');
        
        if (textField && textPeriod) {
            textField.addEventListener('change', function() {
                const value = this.value;
                if (value && value.startsWith('experience') && !textPeriod.value) {
                    textPeriod.value = 'all_time';
                }
            });
        }
    }
    
    function initSearchableSelects() {
        const areaSearch = document.getElementById('area-search');
        const areaList = document.getElementById('area-list');
        const areaSelect = document.getElementById('area');
        const areaContainer = document.getElementById('area-select-container');
        
        if (!areaSearch || !areaList) return;
        
        areaSearch.addEventListener('focus', function() {
            areaList.classList.add('active');
        });
        
        document.addEventListener('click', function(e) {
            if (!areaContainer.contains(e.target)) {
                areaList.classList.remove('active');
            }
        });
        
        areaSearch.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const options = areaList.querySelectorAll('.searchable-select-option');
            
            options.forEach(option => {
                const text = option.textContent.toLowerCase();
                if (text.includes(searchTerm)) {
                    option.classList.remove('hidden');
                } else {
                    option.classList.add('hidden');
                }
            });
        });
        
        const options = areaList.querySelectorAll('.searchable-select-option');
        options.forEach(option => {
            option.addEventListener('click', function() {
                const value = this.getAttribute('data-value');
                const text = this.textContent;
                
                areaSelect.value = value;
                areaSearch.value = text.replace('📍 ', '');
                
                options.forEach(opt => opt.classList.remove('selected'));
                this.classList.add('selected');
                
                areaList.classList.remove('active');
            });
        });
    }

    function initKeywordSuggest() {
        const input = document.getElementById('text');
        const list = document.getElementById('keyword-suggest-list');
        const container = document.getElementById('keyword-suggest-container');
        const roleSelect = document.getElementById('professional_role');

        if (!input || !list || !container) return;

        let debounceTimer = null;
        let activeController = null;

        function hideList() {
            list.classList.remove('active');
            list.innerHTML = '';
        }

        function renderSuggestions(data) {
            list.innerHTML = '';
            const keywords = data.keywords || [];
            const roles = data.roles || [];

            if (!keywords.length && !roles.length) {
                hideList();
                return;
            }

            if (keywords.length) {
                const label = document.createElement('div');
                label.className = 'suggest-section-label';
                label.textContent = 'Ключевые слова';
                list.appendChild(label);

                keywords.forEach(item => {
                    const option = document.createElement('div');
                    option.className = 'searchable-select-option suggest-keyword';
                    option.textContent = item.text;
                    option.addEventListener('click', () => {
                        input.value = item.text;
                        hideList();
                    });
                    list.appendChild(option);
                });
            }

            if (roles.length) {
                const label = document.createElement('div');
                label.className = 'suggest-section-label';
                label.textContent = 'Профессиональные роли';
                list.appendChild(label);

                roles.forEach(item => {
                    const option = document.createElement('div');
                    option.className = 'searchable-select-option suggest-role';
                    option.textContent = item.text;
                    option.addEventListener('click', () => {
                        input.value = item.text;
                        if (roleSelect) {
                            roleSelect.value = item.id;
                        }
                        hideList();
                    });
                    list.appendChild(option);
                });
            }

            list.classList.add('active');
        }

        async function fetchSuggestions(query) {
            if (activeController) {
                activeController.abort();
            }
            activeController = new AbortController();

            try {
                const response = await fetch(
                    `/api/suggest/keywords?q=${encodeURIComponent(query)}`,
                    { signal: activeController.signal }
                );
                if (!response.ok) {
                    hideList();
                    return;
                }
                const data = await response.json();
                renderSuggestions(data);
            } catch (error) {
                if (error.name !== 'AbortError') {
                    hideList();
                }
            }
        }

        input.addEventListener('focus', function() {
            const query = this.value.trim();
            if (query.length >= 2) {
                fetchSuggestions(query);
            }
        });

        input.addEventListener('input', function() {
            const query = this.value.trim();
            clearTimeout(debounceTimer);

            if (query.length < 2) {
                hideList();
                return;
            }

            debounceTimer = setTimeout(() => fetchSuggestions(query), 300);
        });

        document.addEventListener('click', function(e) {
            if (!container.contains(e.target)) {
                hideList();
            }
        });
    }

    function applyPrefillFromServer() {
        if (!window.HH_PREFILL || !form) return;
        applyPrefill(window.HH_PREFILL);
    }

    function applyPrefillFromUrl() {
        if (!form) return;
        const params = Object.fromEntries(new URLSearchParams(window.location.search));
        if (Object.keys(params).length) {
            applyPrefill(params);
        }
    }

    function applyPrefill(values) {
        Object.entries(values).forEach(([name, value]) => {
            if (!value) return;
            const field = form.elements.namedItem(name);
            if (!field) return;
            if (field instanceof RadioNodeList) {
                [...field].forEach(node => {
                    if (node.value === value) node.checked = true;
                });
            } else {
                field.value = value;
            }
        });

        const areaSelect = document.getElementById('area');
        const areaSearch = document.getElementById('area-search');
        if (areaSelect && areaSearch && areaSelect.value) {
            const selected = areaSelect.options[areaSelect.selectedIndex];
            if (selected) {
                areaSearch.value = selected.text.replace('📍 ', '');
            }
        }
    }

    function buildShareUrl() {
        const params = new URLSearchParams(new FormData(form));
        [...params.entries()].forEach(([key, value]) => {
            if (!value) params.delete(key);
        });
        return `${window.location.origin}/?${params.toString()}`;
    }

    function updateShareUrl() {
        const url = buildShareUrl();
        window.history.replaceState({}, '', url);
    }
    
    function setLoading(loading) {
        if (loading) {
            calculateBtn.disabled = true;
            calculateBtn.querySelector('.btn-text').style.display = 'none';
            calculateBtn.querySelector('.btn-loader').style.display = 'inline';
        } else {
            calculateBtn.disabled = false;
            calculateBtn.querySelector('.btn-text').style.display = 'inline';
            calculateBtn.querySelector('.btn-loader').style.display = 'none';
        }
    }
    
    function showResults(data) {
        document.getElementById('vacancies-count').textContent = formatNumber(data.vacancies_count);
        document.getElementById('resumes-count').textContent = formatNumber(data.resumes_count);
        document.getElementById('ratio-value').textContent = data.ratio;
        document.getElementById('difference-value').textContent = formatNumber(data.difference);
        
        const date = new Date(data.timestamp);
        document.getElementById('timestamp').textContent = date.toLocaleString('ru-RU');
        
        const textInput = document.getElementById('text');
        const queryLabel = textInput && textInput.value ? textInput.value : 'запрос';
        if (data.query_signature) {
            document.getElementById('trends-link').href =
                `/trends?signature=${encodeURIComponent(data.query_signature)}&query=${encodeURIComponent(queryLabel)}`;
        }

        if (data.debug && debugContainer) {
            document.getElementById('debug-vacancies-note').textContent = data.debug.vacancies.note;
            document.getElementById('debug-resumes-note').textContent = data.debug.resumes.note;
            const vacanciesUrl = document.getElementById('debug-vacancies-url');
            const resumesUrl = document.getElementById('debug-resumes-url');
            vacanciesUrl.href = data.debug.vacancies.url;
            vacanciesUrl.textContent = data.debug.vacancies.url;
            resumesUrl.href = data.debug.resumes.url;
            resumesUrl.textContent = data.debug.resumes.url;
            debugContainer.style.display = 'block';
        }
        
        resultsContainer.style.display = 'block';
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    function hideResults() {
        resultsContainer.style.display = 'none';
        if (debugContainer) debugContainer.style.display = 'none';
    }
    
    function showError(message) {
        errorMessage.querySelector('p').textContent = message;
        errorMessage.style.display = 'block';
    }
    
    function hideError() {
        errorMessage.style.display = 'none';
    }
    
    function formatNumber(num) {
        if (num === undefined || num === null) return '-';
        return num.toLocaleString('ru-RU');
    }
});
