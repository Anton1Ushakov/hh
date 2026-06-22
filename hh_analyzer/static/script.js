/**
 * Calculator page — labor market analytics
 */

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('calculator-form');
    const resultsContainer = document.getElementById('results');
    const errorMessage = document.getElementById('error-message');
    const calculateBtn = document.getElementById('calculate-btn');

    const chartFont = {
        family: 'Inter, system-ui, sans-serif',
        size: 11,
    };

    const chartColors = {
        vacancy: 'hsl(240, 5.9%, 10%)',
        resume: 'hsl(240, 3.8%, 46.1%)',
        grid: 'hsl(240, 5.9%, 90%)',
        muted: 'hsl(240, 3.8%, 46.1%)',
    };

    let marketChart = null;
    let skillsChart = null;
    let salaryExpChart = null;

    initSearchableSelects();
    initKeywordSuggest();
    applyPrefillFromServer();
    applyPrefillFromUrl();

    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();

            setLoading(true);
            hideResults();
            hideError();

            const formData = new FormData(form);
            const experience = formData.get('vacancy_experience');
            if (experience) {
                formData.set('resume_experience', experience);
            }
            for (const [key, value] of [...formData.entries()]) {
                if (value === '') {
                    formData.delete(key);
                }
            }

            try {
                const response = await fetch('/api/calculate', {
                    method: 'POST',
                    body: formData,
                });

                const data = await response.json();

                if (data.success) {
                    showResults(data);
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
                option.classList.toggle('hidden', !text.includes(searchTerm));
            });
        });

        const options = areaList.querySelectorAll('.searchable-select-option');
        options.forEach(option => {
            option.addEventListener('click', function() {
                const value = this.getAttribute('data-value');
                const text = this.textContent.trim();

                areaSelect.value = value;
                areaSearch.value = text;

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
                    { signal: activeController.signal },
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
        if (!window.APP_PREFILL || !form) return;
        applyPrefill(window.APP_PREFILL);
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
                areaSearch.value = selected.text.trim();
            }
        }

        const experienceField = document.getElementById('vacancy_experience');
        if (experienceField && values.resume_experience && !values.vacancy_experience) {
            experienceField.value = values.resume_experience;
        }
    }

    function setLoading(loading) {
        if (!calculateBtn) return;
        const btnText = calculateBtn.querySelector('.btn-text');
        const btnLoader = calculateBtn.querySelector('.btn-loader');

        calculateBtn.disabled = loading;
        btnText.classList.toggle('hidden', loading);
        btnLoader.classList.toggle('hidden', !loading);
    }

    function destroyChart(chart) {
        if (chart) {
            chart.destroy();
        }
        return null;
    }

    function defaultChartOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        font: chartFont,
                        color: chartColors.muted,
                        boxWidth: 10,
                        boxHeight: 10,
                        usePointStyle: true,
                    },
                },
                tooltip: {
                    backgroundColor: 'hsl(240, 5.9%, 10%)',
                    titleFont: chartFont,
                    bodyFont: chartFont,
                    padding: 10,
                    cornerRadius: 6,
                },
            },
        };
    }

    function renderMarketChart(vacancies, resumes) {
        const canvas = document.getElementById('market-chart');
        if (!canvas || typeof Chart === 'undefined') return;

        marketChart = destroyChart(marketChart);
        marketChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: ['Вакансии', 'Резюме'],
                datasets: [{
                    data: [vacancies, resumes],
                    backgroundColor: [chartColors.vacancy, chartColors.resume],
                    borderRadius: 6,
                    barThickness: 48,
                }],
            },
            options: {
                ...defaultChartOptions(),
                plugins: {
                    ...defaultChartOptions().plugins,
                    legend: { display: false },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { ...chartFont, size: 12, weight: '500' }, color: chartColors.muted },
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: chartColors.grid, drawBorder: false },
                        ticks: {
                            font: chartFont,
                            color: chartColors.muted,
                            callback: (value) => formatCompactNumber(value),
                        },
                    },
                },
            },
        });
    }

    function parseSalaryNumber(display) {
        if (!display) return null;
        const digits = display.replace(/[^\d]/g, '');
        return digits ? parseInt(digits, 10) : null;
    }

    function renderSalaryExpChart(rows) {
        const wrap = document.getElementById('insights-salary-exp-chart-wrap');
        const canvas = document.getElementById('salary-exp-chart');
        if (!wrap || !canvas || typeof Chart === 'undefined') return;

        const dataRows = rows.filter((row) => row.median_from || row.median_to || row.median_display);
        if (!dataRows.length) {
            wrap.classList.add('hidden');
            salaryExpChart = destroyChart(salaryExpChart);
            return;
        }

        wrap.classList.remove('hidden');
        salaryExpChart = destroyChart(salaryExpChart);

        const labels = dataRows.map((row) => row.name);
        const values = dataRows.map((row) => {
            if (row.median_from && row.median_to) {
                return Math.round((row.median_from + row.median_to) / 2);
            }
            return row.median_from || row.median_to || parseSalaryNumber(row.median_display);
        });

        salaryExpChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Медиана, ₽',
                    data: values,
                    backgroundColor: chartColors.vacancy,
                    borderRadius: 4,
                }],
            },
            options: {
                indexAxis: 'y',
                ...defaultChartOptions(),
                plugins: {
                    ...defaultChartOptions().plugins,
                    legend: { display: false },
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: { color: chartColors.grid, drawBorder: false },
                        ticks: {
                            font: chartFont,
                            color: chartColors.muted,
                            callback: (value) => formatCompactNumber(value),
                        },
                    },
                    y: {
                        grid: { display: false },
                        ticks: { font: chartFont, color: chartColors.muted },
                    },
                },
            },
        });
    }

    function renderSkillsChart(skills) {
        const wrap = document.getElementById('insights-skills-chart-wrap');
        const canvas = document.getElementById('skills-chart');
        if (!wrap || !canvas || typeof Chart === 'undefined') return;

        const top = skills.slice(0, 8);
        if (!top.length) {
            wrap.classList.add('hidden');
            skillsChart = destroyChart(skillsChart);
            return;
        }

        wrap.classList.remove('hidden');
        skillsChart = destroyChart(skillsChart);

        skillsChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: top.map((s) => s.name),
                datasets: [{
                    data: top.map((s) => s.percent),
                    backgroundColor: 'hsl(240, 4.8%, 85%)',
                    hoverBackgroundColor: chartColors.vacancy,
                    borderRadius: 4,
                }],
            },
            options: {
                indexAxis: 'y',
                ...defaultChartOptions(),
                plugins: {
                    ...defaultChartOptions().plugins,
                    legend: { display: false },
                    tooltip: {
                        ...defaultChartOptions().plugins.tooltip,
                        callbacks: {
                            label: (ctx) => `${ctx.parsed.x}%`,
                        },
                    },
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        grid: { color: chartColors.grid, drawBorder: false },
                        ticks: {
                            font: chartFont,
                            color: chartColors.muted,
                            callback: (value) => `${value}%`,
                        },
                    },
                    y: {
                        grid: { display: false },
                        ticks: { font: chartFont, color: chartColors.muted },
                    },
                },
            },
        });
    }

    function showResults(data) {
        document.getElementById('vacancies-count').textContent = formatNumber(data.vacancies_count);
        document.getElementById('resumes-count').textContent = formatNumber(data.resumes_count);
        document.getElementById('ratio-value').textContent = data.ratio;
        document.getElementById('difference-value').textContent = formatNumber(data.difference);

        const date = new Date(data.timestamp);
        document.getElementById('timestamp').textContent = date.toLocaleString('ru-RU');

        renderMarketChart(data.vacancies_count, data.resumes_count);
        renderInsights(data.insights, data.vacancies_count);

        resultsContainer.classList.remove('hidden');
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function renderInsights(insights, vacanciesCount) {
        const panel = document.getElementById('insights-panel');
        const salaryRange = document.getElementById('insights-salary-range');
        const salaryMeta = document.getElementById('insights-salary-meta');
        const skillsMeta = document.getElementById('insights-skills-meta');
        const skillsList = document.getElementById('insights-skills-list');
        const salaryByExpTable = document.getElementById('insights-salary-by-exp');
        const salaryByExpBody = document.getElementById('insights-salary-by-exp-body');

        if (!panel) return;

        if (!vacanciesCount) {
            panel.classList.add('hidden');
            return;
        }

        panel.classList.remove('hidden');

        if (!insights) {
            salaryRange.textContent = 'Нет данных';
            salaryMeta.textContent = 'Перезапустите сервер с актуальной версией приложения';
            skillsMeta.textContent = '';
            skillsList.innerHTML = '';
            salaryByExpTable.classList.add('hidden');
            salaryByExpBody.innerHTML = '';
            renderSalaryExpChart([]);
            renderSkillsChart([]);
            return;
        }

        const salary = insights.salary || {};
        const salaryByExperience = insights.salary_by_experience || [];
        const skills = insights.top_skills || [];
        const hasSalary = Boolean(salary.display);
        const hasSkills = skills.length > 0;

        if (hasSalary) {
            salaryRange.textContent = salary.display;
            const parts = [];
            if (salary.median_display) {
                parts.push(`Медиана: ${salary.median_display}`);
            }
            if (salary.with_salary_percent != null) {
                parts.push(`Указана в ${salary.with_salary_percent}% из ${salary.sample_size} вакансий выборки`);
            }
            salaryMeta.textContent = parts.join(' · ');
        } else {
            salaryRange.textContent = 'Зарплата в выборке не указана';
            salaryMeta.textContent = salary.sample_size
                ? `Проверено ${salary.sample_size} вакансий`
                : '';
        }

        if (salaryByExpBody && salaryByExpTable) {
            salaryByExpBody.innerHTML = '';
            const rowsWithSalary = salaryByExperience.filter((row) => row.display);
            if (rowsWithSalary.length) {
                salaryByExpTable.classList.remove('hidden');
                rowsWithSalary.forEach((row) => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${escapeHtml(row.name)}</td>
                        <td>${escapeHtml(row.display || '—')}</td>
                        <td>${escapeHtml(row.median_display || '—')}</td>
                    `;
                    salaryByExpBody.appendChild(tr);
                });
                renderSalaryExpChart(rowsWithSalary);
            } else {
                salaryByExpTable.classList.add('hidden');
                renderSalaryExpChart([]);
            }
        }

        skillsList.innerHTML = '';
        if (hasSkills) {
            skillsMeta.textContent = insights.skills_sample_size
                ? `По ${insights.skills_sample_size} вакансиям с навыками в описании`
                : '';
            skills.forEach((skill, index) => {
                const item = document.createElement('li');
                item.className = 'insights-skill-item';
                item.innerHTML = `
                    <span class="insights-skill-rank">${index + 1}</span>
                    <span class="insights-skill-name">${escapeHtml(skill.name)}</span>
                    <span class="insights-skill-stats">${skill.percent}%</span>
                    <div class="insights-skill-bar">
                        <div class="insights-skill-bar-fill" style="width: ${Math.min(skill.percent, 100)}%"></div>
                    </div>
                `;
                skillsList.appendChild(item);
            });
            renderSkillsChart(skills);
        } else {
            skillsMeta.textContent = 'Навыки в выборке не заполнены';
            renderSkillsChart([]);
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function hideResults() {
        resultsContainer.classList.add('hidden');
        marketChart = destroyChart(marketChart);
        skillsChart = destroyChart(skillsChart);
        salaryExpChart = destroyChart(salaryExpChart);
    }

    function showError(message) {
        errorMessage.querySelector('p').textContent = message;
        errorMessage.classList.remove('hidden');
    }

    function hideError() {
        errorMessage.classList.add('hidden');
    }

    function formatNumber(num) {
        if (num === undefined || num === null) return '-';
        return num.toLocaleString('ru-RU');
    }

    function formatCompactNumber(num) {
        if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
        if (num >= 1_000) return `${(num / 1_000).toFixed(0)}k`;
        return num;
    }
});
