"use strict";
const config = JSON.parse(document.getElementById("analysis-data").textContent);
const byId = id => document.getElementById(id);
let state = config.job;
let moves = [...state.moves];
let selected = -1;
let solutionMode = false;
let chart = null;
const terminal = () => ["complete", "error"].includes(state.state);

function evaluation(score, mate) {
    if (mate !== null && mate !== undefined) {
        if (mate === 0) return score > 0 ? "Mat a favor" : "Mat en contra";
        return `Mat ${score > 0 ? "a favor" : "en contra"} en ${Math.abs(mate)}`;
    }
    return `${score >= 0 ? "+" : ""}${(score / 100).toLocaleString("ca", {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
}

function choosePosition(index) {
    const maximum = state.state === "complete" ? moves.length : moves.length - 1;
    selected = Math.max(-1, Math.min(index, maximum));
    solutionMode = false;
    render();
}

function renderBoard() {
    const isFinal = state.state === "complete" && selected === moves.length;
    const move = moves[selected];
    const board = byId("board");
    if (isFinal || selected === -1) {
        board.innerHTML = isFinal ? state.final_svg : state.initial_svg;
        byId("position-label").textContent = isFinal ? "Posició final" : "Posició inicial";
        const last = moves[moves.length - 1];
        byId("score-label").textContent = isFinal && last ? evaluation(last.score, state.final_checkmate ? 0 : last.mate) : "Sense avaluació";
        byId("move-comment").textContent = isFinal
            ? `Fi de la partida · ${state.result === "*" ? "Resultat no indicat al PGN" : state.result}` : "";
    } else if (move) {
        const img = document.createElement("img");
        img.src = config.imageBase + (solutionMode ? move.solution_image : move.image);
        img.alt = `Posició abans de ${move.move_number}${move.mover === "white" ? "." : "…"} ${move.san}`;
        board.replaceChildren(img);
        byId("position-label").textContent = `${move.move_number}${move.mover === "white" ? "." : "…"} ${move.san}`;
        byId("score-label").textContent = evaluation(move.score, move.mate);
        byId("move-comment").textContent = move.assessment
            ? `${move.assessment.text} · Pèrdua: ${move.assessment.loss_percent.toLocaleString("ca")} pp (${move.assessment.loss_cp} cp)`
            : "Jugada del rival";
    }
    const list = byId("alternatives");
    list.replaceChildren();
    if (solutionMode && move) {
        for (const alternative of move.alternatives) {
            const item = document.createElement("li");
            item.textContent = `${alternative.san}: ${evaluation(alternative.score, alternative.mate)}`;
            list.append(item);
        }
        if (!move.alternatives.length) {
            const item = document.createElement("li");
            item.textContent = "No hi ha alternatives candidates dins de la tolerància configurada.";
            list.append(item);
        }
    }
    list.hidden = !solutionMode;
    byId("initial").disabled = selected === -1;
    byId("previous").disabled = selected === -1;
    byId("next").disabled = selected >= (state.state === "complete" ? moves.length : moves.length - 1);
    byId("final").disabled = state.state !== "complete" || isFinal;
    byId("solution").disabled = isFinal || !move || !move.solution_image;
    byId("solution").textContent = solutionMode ? "Amaga les alternatives" : "Mostra les alternatives";
}

function renderTable() {
    const tbody = byId("moves-table").querySelector("tbody");
    tbody.replaceChildren();
    const rows = new Map();
    for (const move of moves) {
        let row = rows.get(move.move_number);
        if (!row) {
            row = document.createElement("tr");
            for (let i = 0; i < 4; i++) row.append(document.createElement("td"));
            row.cells[0].textContent = `${move.move_number}.`;
            tbody.append(row);
            rows.set(move.move_number, row);
        }
        const button = document.createElement("button");
        button.type = "button";
        button.className = "move-button" + (selected === move.index ? " selected" : "");
        button.textContent = move.san;
        button.setAttribute("aria-label", `${move.move_number}${move.mover === "white" ? ". Blanques" : ". Negres"}: ${move.san}`);
        if (selected === move.index) button.setAttribute("aria-current", "step");
        button.addEventListener("click", () => choosePosition(move.index));
        row.cells[move.mover === "white" ? 1 : 2].append(button);
        if (move.assessment) {
            row.cells[3].textContent = move.assessment.text;
            row.cells[3].className = `comment-cell ${move.assessment.category}`;
        }
    }
    byId("moves-empty").hidden = moves.length !== 0;
}

function renderStatus() {
    byId("progress").value = state.available;
    byId("spinner").hidden = terminal();
    const status = byId("analysis-status");
    const unit = state.total === 1 ? "mitja jugada" : "mitges jugades";
    if (state.state === "queued") status.textContent = "Anàlisi en cua. Començarà quan acabi la partida anterior…";
    else if (state.state === "complete") status.textContent = `Anàlisi completada · ${state.total} de ${state.total} ${unit}`;
    else if (state.state === "error") status.textContent = `Anàlisi aturada · ${state.available} de ${state.total} ${unit} disponibles`;
    else if (!moves.length) status.textContent = "Stockfish està calculant la primera jugada…";
    else status.textContent = `Calculant la jugada següent · ${state.available} de ${state.total} ${unit} disponibles`;
    byId("analysis-error").hidden = !state.error;
    byId("analysis-error").textContent = state.error || "";
}

function renderSummary() {
    byId("analysis-summary").hidden = state.state !== "complete";
    if (state.state !== "complete") return;
    const counts = {best: 0, good: 0, inaccuracy: 0, mistake: 0, blunder: 0};
    for (const move of moves) {
        if (!move.assessment) continue;
        const category = move.assessment.category === "excellent" ? "good" : move.assessment.category;
        if (Object.hasOwn(counts, category)) counts[category]++;
    }
    for (const [category, count] of Object.entries(counts)) {
        byId(`summary-${category}`).textContent = count.toLocaleString("ca");
    }
    byId("summary-total").textContent = Object.values(counts).reduce((sum, count) => sum + count, 0).toLocaleString("ca");
}

function render() {
    renderStatus();
    renderBoard();
    renderTable();
    renderSummary();
    if (chart) {
        const visible = moves.slice(0, selected < 0 ? 0 : selected + 1);
        chart.data.labels = visible.map(move => `${move.move_number}${move.mover === "white" ? "." : "…"} ${move.san}`);
        chart.data.datasets[0].data = visible.map(move => Math.max(-15, Math.min(15, move.score / 100)));
        chart.update("none");
    }
}

async function poll() {
    try {
        const response = await fetch(`${config.statusUrl}?since=${moves.length}`, {cache: "no-store"});
        if (response.status === 404) {
            state.state = "error";
            state.error = "Aquesta anàlisi ja no és al servidor. Pot haver-se reiniciat; comença una anàlisi nova.";
            render();
            return;
        }
        if (!response.ok) throw new Error("No s'ha pogut consultar el progrés.");
        const incoming = await response.json();
        moves.push(...incoming.moves);
        state = incoming;
        render();
    } catch {
        byId("analysis-status").textContent = "S'ha perdut la connexió. Tornant a consultar el progrés…";
    }
    if (!terminal()) window.setTimeout(poll, 700);
}

byId("initial").addEventListener("click", () => choosePosition(-1));
byId("previous").addEventListener("click", () => choosePosition(selected - 1));
byId("next").addEventListener("click", () => choosePosition(selected + 1));
byId("final").addEventListener("click", () => choosePosition(moves.length));
byId("solution").addEventListener("click", () => {
    if (byId("solution").disabled) return;
    solutionMode = !solutionMode;
    renderBoard();
});
document.addEventListener("keydown", event => {
    if (event.target.closest("input, textarea, select, button, a, summary")) return;
    if (event.key === "ArrowRight") { event.preventDefault(); choosePosition(selected + 1); }
    if (event.key === "ArrowLeft") { event.preventDefault(); choosePosition(selected - 1); }
    if (event.code === "Space") { event.preventDefault(); byId("solution").click(); }
});
function setupChart() {
    if (chart) return;
    if (typeof Chart !== "undefined") {
        chart = new Chart(byId("score-chart"), {
            type: "line",
            data: {labels: [], datasets: [{label: "Avaluació en peons", data: [], borderColor: "#27684e", tension: 0.15, pointRadius: 2}]},
            options: {locale: "ca", responsive: true, maintainAspectRatio: false, animation: false, scales: {y: {suggestedMin: -1, suggestedMax: 1}}, plugins: {legend: {display: false}}},
        });
        byId("chart-status").hidden = true;
        byId("score-chart").parentElement.hidden = false;
        render();
    } else {
        byId("chart-status").hidden = false;
        byId("score-chart").parentElement.hidden = true;
    }
}
byId("chart-library").addEventListener("load", setupChart);
setupChart();
render();
if (!terminal()) poll();
