"use strict";
const search = document.querySelector("#search");
const statusFilter = document.querySelector("#status");
const cards = [...document.querySelectorAll(".report-card")];
const months = [...document.querySelectorAll(".month-filter")];
let selectedMonth = "";
function filterReports() {
  const term = search.value.trim().toLocaleLowerCase();
  let visible = 0;
  for (const card of cards) {
    const matches = (!selectedMonth || card.dataset.month === selectedMonth)
      && (!statusFilter.value || card.dataset.status === statusFilter.value)
      && card.textContent.toLocaleLowerCase().includes(term);
    card.hidden = !matches;
    if (matches) visible += 1;
  }
  document.querySelector("#no-results").hidden = visible > 0 || cards.length === 0;
  document.querySelector("#result-count").textContent = cards.length ? `显示 ${visible} / ${cards.length} 份报告` : "";
}
search.addEventListener("input", filterReports);
statusFilter.addEventListener("change", filterReports);
for (const button of months) {
  button.setAttribute("aria-pressed", String(button.dataset.value === selectedMonth));
  button.addEventListener("click", () => {
    selectedMonth = button.dataset.value;
    for (const item of months) {
      const selected = item === button;
      item.classList.toggle("selected", selected);
      item.setAttribute("aria-pressed", String(selected));
    }
    filterReports();
  });
}
filterReports();
