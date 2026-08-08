# EPOS v3.1

Motore RPG narrativo generico con stato autorevole governato da Python, Worldpack intercambiabili,
NPC autonomi, missioni/eventi, memoria, VST e pipeline ComfyUI.

## Avvio rapido
Richiede Python 3.11+.

```bash
python -m venv .venv
pip install -e .
python -m epos_v3.presentation.cli --worldpack worldpacks/resort_world --session-id partita1
```

Nel CLI: `/advance` avanza una fase; `/resume` riprende un checkpoint senza ritirare i dadi.

## Configurazione
Copia `.env.example` in `.env`. Inserisci almeno una chiave LLM per provider reali e configura
ComfyUI per le immagini.

## Test
```bash
pip install -e ".[dev]"
pytest -q
ruff check src tests
mypy --strict src
```

Verificato nel sandbox: 128 test passati e compileall OK.
Ruff/mypy devono essere eseguiti sulla macchina finale.

## Visual pipeline
LLM -> VST -> validazione Python -> WorldState autorevole -> prompt deterministico ->
LoRA dinamiche -> workflow ComfyUI.
