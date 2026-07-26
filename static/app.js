document.addEventListener("DOMContentLoaded", () => {
  // ---- upload page: show chosen file name ----
  document.querySelectorAll(".file-drop input[type='file']").forEach((input) => {
    input.addEventListener("change", () => {
      const nameEl = document.getElementById(`${input.id}-name`);
      const labelEl = document.getElementById(`${input.id}-label`);
      if (input.files && input.files.length > 0) {
        if (nameEl) nameEl.textContent = input.files[0].name;
        if (labelEl) labelEl.textContent = "Selected";
      }
    });
  });

  // ---- results page: tabs ----
  const tabButtons = document.querySelectorAll("[data-tab-target]");
  const tabPanels = document.querySelectorAll("[data-tab-panel]");
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabButtons.forEach((b) => b.classList.remove("active"));
      tabPanels.forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const target = document.querySelector(`[data-tab-panel="${btn.dataset.tabTarget}"]`);
      if (target) target.classList.add("active");
    });
  });

  // ---- results page: stat tiles as status filters ----
  document.querySelectorAll("[data-filter-section]").forEach((section) => {
    const key = section.dataset.filterSection;
    const rows = document.querySelectorAll(`[data-rows-for="${key}"] > table > tbody > tr`);
    const countEl = document.querySelector(`[data-row-count-for="${key}"]`);
    const tiles = section.querySelectorAll("[data-filter]");

    function applyFilter(filter) {
      let visible = 0;
      rows.forEach((row) => {
        const match = filter === "all" || row.dataset.status === filter;
        row.style.display = match ? "" : "none";
        if (match) visible += 1;
      });
      if (countEl) countEl.textContent = `Showing ${visible} of ${rows.length} rows`;
    }

    tiles.forEach((tile) => {
      tile.addEventListener("click", () => {
        tiles.forEach((t) => t.classList.remove("active"));
        tile.classList.add("active");
        applyFilter(tile.dataset.filter);
      });
    });

    applyFilter("all");
  });
});
