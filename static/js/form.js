"use strict";
const form = document.getElementById("analysis-form");
const defaults = JSON.parse(form.dataset.defaults);
const thresholds = ["excellent", "inaccuracy", "mistake", "blunder"];
function validateThresholds() {
    const values = thresholds.map(name => Number(document.getElementById(name).value));
    document.getElementById("blunder").setCustomValidity(
        values.every((value, index) => index === 0 || value > values[index - 1])
            ? "" : "Els llindars han de complir: excel·lent < imprecisió < error < error greu."
    );
}
for (const slider of document.querySelectorAll("input[data-control]")) {
    const input = document.getElementById(slider.dataset.control);
    slider.addEventListener("input", () => { input.value = slider.value; validateThresholds(); });
    input.addEventListener("input", () => { slider.value = input.value; validateThresholds(); });
}
document.getElementById("reset-settings").addEventListener("click", () => {
    for (const [name, value] of Object.entries(defaults)) {
        document.getElementById(name).value = value;
        document.getElementById(`${name}-slider`).value = value;
    }
    validateThresholds();
});
document.getElementById("choose-file").addEventListener("click", () => document.getElementById("pgn-file").click());
document.getElementById("pgn-file").addEventListener("change", async event => {
    const file = event.target.files[0];
    if (!file) return;
    try {
        document.getElementById("pgn").value = await file.text();
        document.getElementById("file-status").textContent = `Fitxer carregat: ${file.name}`;
    } catch {
        document.getElementById("file-status").textContent = "No s'ha pogut llegir el fitxer. Enganxa el PGN al camp de text.";
    }
});
form.addEventListener("submit", () => {
    document.getElementById("submit-button").disabled = true;
    document.getElementById("submit-status").textContent = "Preparant l'anàlisi…";
});
validateThresholds();
