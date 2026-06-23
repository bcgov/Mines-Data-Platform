from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "mxfabric" / "paths.py"
NOTEBOOK = ROOT / "Fabric" / "nb_util_paths.Notebook" / "notebook-content.py"
START = "# >>> MXFABRIC:paths START"
END = "# >>> MXFABRIC:paths END"


def _module_body() -> str:
    text = MODULE.read_text(encoding="utf-8").splitlines()
    # drop the module docstring line (first line) and the blank line after it
    body = "\n".join(text[1:]).strip("\n")
    return body


def _notebook_block() -> str:
    text = NOTEBOOK.read_text(encoding="utf-8")
    block = text.split(START, 1)[1].split(END, 1)[0]
    return block.strip("\n")


def test_notebook_matches_module():
    assert _notebook_block() == _module_body(), (
        "nb_util_paths code drifted from src/mxfabric/paths.py — "
        "regenerate the notebook block from the module."
    )
