/**
 * Main JavaScript for HH.ru Analytics
 */

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('calculator-form');
    const resultsContainer = document.getElementById('results');
    const errorMessage = document.getElementById('error-message');
    const calculateBtn = document.getElementById('calculate-btn');
    
    // Initialize searchable selects
    initSearchableSelects();
    
    // Initialize collapsible sections
    initCollapsibleSections();
    
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Show loading state
            setLoading(true);
            hideResults();
            hideError();
            
            // Collect form data
            const formData = new FormData(form);
            
            try {
                const response = await fetch('/api/calculate', {
                    method: 'POST',
                    body: formData
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
    
    // Initialize collapsible sections
    function initCollapsibleSections() {
        const collapsibles = document.querySelectorAll('.collapsible');
        
        collapsibles.forEach(section => {
            const header = section.querySelector('.collapsible-header');
            
            header.addEventListener('click', function() {
                section.classList.toggle('active');
            });
        });
    }
    
    // Initialize resume text.* triad logic
    initResumeTextTriad();
    
    function initResumeTextTriad() {
        // Auto-set default period when experience field is selected
        const textField = document.getElementById('resume_text_field');
        const textPeriod = document.getElementById('resume_text_period');
        
        if (textField && textPeriod) {
            textField.addEventListener('change', function() {
                const value = this.value;
                // If experience-related field is selected and no period set, default to all_time
                if (value && value.startsWith('experience') && !textPeriod.value) {
                    textPeriod.value = 'all_time';
                }
            });
        }
    }
    
    // Initialize searchable selects
    function initSearchableSelects() {
        const areaSearch = document.getElementById('area-search');
        const areaList = document.getElementById('area-list');
        const areaSelect = document.getElementById('area');
        const areaContainer = document.getElementById('area-select-container');
        
        if (!areaSearch || !areaList) return;
        
        // Show list on focus
        areaSearch.addEventListener('focus', function() {
            areaList.classList.add('active');
        });
        
        // Hide list when clicking outside
        document.addEventListener('click', function(e) {
            if (!areaContainer.contains(e.target)) {
                areaList.classList.remove('active');
            }
        });
        
        // Filter options on input
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
        
        // Select option on click
        const options = areaList.querySelectorAll('.searchable-select-option');
        options.forEach(option => {
            option.addEventListener('click', function() {
                const value = this.getAttribute('data-value');
                const text = this.textContent;
                
                // Update hidden select
                areaSelect.value = value;
                
                // Update search input
                areaSearch.value = text.replace('📍 ', '');
                
                // Update visual selection
                options.forEach(opt => opt.classList.remove('selected'));
                this.classList.add('selected');
                
                // Hide list
                areaList.classList.remove('active');
            });
        });
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
        // Update values
        document.getElementById('vacancies-count').textContent = formatNumber(data.vacancies_count);
        document.getElementById('resumes-count').textContent = formatNumber(data.resumes_count);
        document.getElementById('ratio-value').textContent = data.ratio;
        document.getElementById('difference-value').textContent = formatNumber(data.difference);
        
        // Update timestamp
        const date = new Date(data.timestamp);
        document.getElementById('timestamp').textContent = date.toLocaleString('ru-RU');
        
        // Update trends link
        const textInput = document.getElementById('text');
        if (textInput && textInput.value) {
            document.getElementById('trends-link').href = `/trends?query=${encodeURIComponent(textInput.value)}`;
        }
        
        // Show results
        resultsContainer.style.display = 'block';
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    function hideResults() {
        resultsContainer.style.display = 'none';
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
