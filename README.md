# CoaChess

Aplicació web en català per analitzar partides d'escacs PGN amb Python, Flask i
Stockfish. Mostra les jugades a mesura que es calculen, amb alternatives sobre
el tauler, comentaris i un gràfic d'avaluació.

## Instal·lació

Necessites [uv](https://docs.astral.sh/uv/getting-started/installation/).
Des de l'arrel del repositori:

```bash
uv venv --python 3.10
uv pip install -r requirements.txt
uv run python scripts/install_stockfish.py
./run.sh
```

Obre **http://127.0.0.1:5000**. Si ja tens `.venv`, omet la primera ordre.
Stockfish s'instal·la a `engines/stockfish/`, amb verificació SHA-256 i UCI.
L'instal·lador admet Linux x86-64/ARM64, macOS i Windows de 64 bits.

Amb `pip`, crea i activa un entorn amb `python3 -m venv .venv`, instal·la
`requirements.txt` i executa `python scripts/install_stockfish.py`.
Sense Bash (per exemple, a Windows), arrenca amb:

```bash
uv run python -m flask --app coachess run
```

## Ús

- Obre un fitxer `.pgn` o enganxa'n el contingut; tria blanques o negres.
- Ajusta els controls o mantén els valors inicials: **0,5 s per cerca**, **3
  candidates** i llindars de **5/10/15 punts percentuals** per a imprecisió,
  error i error greu, inspirats en [Lichess](https://lichess.org/page/accuracy).
- Explora les jugades disponibles amb els botons, la taula o les tecles **←/→**.
  **Espai** mostra les alternatives; **Final** mostra el tauler final.
  La vista només avança quan ho decideixes, encara que continuï l'anàlisi.
- En acabar, un resum compta les millors jugades, les bones (incloent-hi les
  excel·lents), les imprecisions, els errors i els errors greus del jugador.

S'analitza la primera partida i la línia principal. Els scores positius
favoreixen el jugador seleccionat. Els treballs es processen en cua i es
mantenen en memòria: reiniciar el servidor elimina les anàlisis disponibles.

## Raspberry Pi amb Tailscale

Fes servir **Raspberry Pi OS de 64 bits** i copia el repositori a `~/coachess`.
Instal·la uv i, des d'aquesta carpeta:

```bash
uv venv --python 3.10
uv pip install -r requirements-server.txt
uv run python scripts/install_stockfish.py
```

Instal·la i connecta Tailscale segons la
[guia oficial per a Linux](https://tailscale.com/docs/install/linux):

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale ip -4
uv run python server.py --host 0.0.0.0
```

Des d'un mòbil o ordinador connectat a la mateixa xarxa Tailscale, obre
**`http://IP_TAILSCALE_DE_LA_PI:5000`**; per exemple,
`http://100.101.102.103:5000`. Waitress escolta a les interfícies de la Pi,
inclosa la de Tailscale.

Per arrencar automàticament (primer atura el servidor manual amb `Ctrl+C`):

```bash
mkdir -p ~/.config/systemd/user
cp deploy/coachess.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now coachess.service
sudo loginctl enable-linger "$USER"
```

El servei assumeix el repositori a `~/coachess`; adapta les rutes si el tens en
una altra carpeta. Logs: `journalctl --user -u coachess.service -f`.
Després d'actualitzar: `systemctl --user restart coachess.service`.
La instal·lació s'ha verificat en Linux x86-64, però encara no en una Pi física.

## Configuració

- `STOCKFISH_PATH`: ruta opcional a un motor propi. Per defecte es busca dins
  del repositori i, després, al `PATH` del sistema.
- `SECRET_KEY`: clau opcional de sessió de Flask.
- `server.py --host … --port …`: adreça i port del servidor Waitress.
  Per defecte escolta a `127.0.0.1:5000`.
- `./run.sh --debug`: desenvolupament amb recàrrega automàtica.

Els SVG generats es desen a `static/<partida>/` i Git els ignora. El CSS i el
JavaScript són locals; el gràfic carrega Chart.js des d'un CDN.

## Desenvolupament i tests

`tests/` conté els tests de regressió, les proves de navegador i el notebook
exploratori `test.ipynb`, que conserva experiments antics i no és necessari
per executar l'app.

```bash
uv run python -m unittest discover -s tests -v
```

Prova opcional de navegador, amb l'app en marxa:

```bash
uv run --with playwright playwright install chromium
uv run --with playwright python tests/browser_smoke.py
```
