# Installazione EPOS v3.1 su Windows

1. Installa Python 3.11 o 3.12 e verifica con `python --version`.
2. Crea una nuova cartella, per esempio `C:\EPOS`, ed estrai qui lo ZIP.
3. Apri PowerShell dentro `C:\EPOS` ed esegui:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

Se PowerShell blocca l'attivazione:
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

4. Copia `.env.example` in `.env` e inserisci `OPENAI_API_KEY` oppure `GEMINI_API_KEY`.
Non condividere `.env`.

5. Per le immagini avvia ComfyUI. Il default EPOS è `127.0.0.1:8188`.
Installa il checkpoint indicato in `worldpacks/resort_world/comfy_workflow_image.json` e queste LoRA:
- Expressive_H-000001.safetensors
- Zatanna_-_DC_Animated_Universe.safetensors
- stsSmith-10e.safetensors
- stsDebbie-10e.safetensors
- FantasyWorldPonyV2.safetensors
- alice_mitchell_milf_catchers_lora.safetensors

6. Verifica:
```powershell
pip install -e ".[dev]"
pytest -q
ruff check src tests
mypy --strict src
```

7. Avvia:
```powershell
epos --worldpack worldpacks/resort_world --session-id partita1
```

Se `epos` non viene trovato:
```powershell
python -m epos_v3.presentation.cli --worldpack worldpacks/resort_world --session-id partita1
```

Durante la partita `/advance` avanza una fase; `/resume` riprende un turno interrotto.
Le normali azioni non fanno avanzare il tempo.
