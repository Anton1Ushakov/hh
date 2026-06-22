document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('dict-search');
    const groupsRoot = document.getElementById('dict-groups');
    const noResults = document.getElementById('dict-no-results');
    const expandAllBtn = document.getElementById('dict-expand-all');
    const collapseAllBtn = document.getElementById('dict-collapse-all');
    const showVariantsToggle = document.getElementById('dict-show-variants');

    if (!searchInput || !groupsRoot) {
        return;
    }

    const groups = Array.from(groupsRoot.querySelectorAll('.dict-group'));

    function setOpenState(selector, open) {
        groupsRoot.querySelectorAll(selector).forEach((el) => {
            el.open = open;
        });
    }

    function applyVariantsVisibility() {
        const showAll = Boolean(showVariantsToggle?.checked);
        groupsRoot.classList.toggle('dict-show-variants', showAll);
    }

    expandAllBtn?.addEventListener('click', () => {
        setOpenState('.dict-group, .dict-role, .dict-seniority', true);
    });

    collapseAllBtn?.addEventListener('click', () => {
        setOpenState('.dict-group, .dict-role, .dict-seniority', false);
    });

    showVariantsToggle?.addEventListener('change', applyVariantsVisibility);
    applyVariantsVisibility();

    function matchEntry(entry, query, contextText) {
        const entryLabel = entry.dataset.entryLabel || '';
        const variants = Array.from(entry.querySelectorAll('.dict-variant-item'));
        let visibleVariants = 0;

        variants.forEach((variant) => {
            const titleText = variant.dataset.title || '';
            const match = !query
                || contextText.includes(query)
                || entryLabel.includes(query)
                || titleText.includes(query);
            variant.hidden = !match;
            if (match) {
                visibleVariants += 1;
            }
        });

        const rowText = entry.querySelector('.dict-entry-name')?.textContent?.toLowerCase() || '';
        return !query
            || contextText.includes(query)
            || entryLabel.includes(query)
            || rowText.includes(query)
            || visibleVariants > 0;
    }

    function filterEntriesList(list, query, contextText) {
        const entries = Array.from(list.querySelectorAll('.dict-entry'));
        let visible = 0;

        entries.forEach((entry) => {
            const match = matchEntry(entry, query, contextText);
            entry.hidden = !match;
            if (match) {
                visible += 1;
            }
        });

        return visible;
    }

    searchInput.addEventListener('input', () => {
        const query = searchInput.value.trim().toLowerCase();
        let visibleGroups = 0;

        groups.forEach((group) => {
            const groupTitle = group.querySelector('.dict-group-title')?.textContent?.toLowerCase() || '';
            const roles = Array.from(group.querySelectorAll('.dict-role'));
            let visibleRoles = 0;

            roles.forEach((role) => {
                const roleTitle = role.querySelector('.dict-role-title')?.textContent?.toLowerCase() || '';
                const contextText = `${groupTitle} ${roleTitle}`;
                const seniorityLevels = Array.from(role.querySelectorAll('.dict-seniority'));
                let visibleInRole = 0;

                seniorityLevels.forEach((level) => {
                    const levelLabel = level.dataset.seniorityLabel || '';
                    const levelContext = `${contextText} ${levelLabel}`;
                    const visible = filterEntriesList(level, query, levelContext);
                    const levelMatch = !query || levelContext.includes(query) || visible > 0;
                    level.hidden = !levelMatch;
                    if (levelMatch) {
                        visibleInRole += visible;
                        if (query) {
                            level.open = true;
                        }
                    }
                });

                const flatList = role.querySelector(':scope > .dict-role-body > .dict-entries-list');
                if (flatList) {
                    visibleInRole += filterEntriesList(flatList, query, contextText);
                }

                const roleMatch = !query || contextText.includes(query) || visibleInRole > 0;
                role.hidden = !roleMatch;
                if (roleMatch) {
                    visibleRoles += 1;
                    if (query) {
                        role.open = true;
                    }
                }
            });

            const groupMatch = !query || groupTitle.includes(query) || visibleRoles > 0;
            group.hidden = !groupMatch;
            if (groupMatch) {
                visibleGroups += 1;
                if (query) {
                    group.open = true;
                }
            }
        });

        if (noResults) {
            noResults.hidden = visibleGroups > 0;
        }
    });
});
