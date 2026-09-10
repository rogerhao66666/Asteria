from __future__ import annotations

import contextlib
import io
import traceback
from dataclasses import dataclass

from .api import AuthoringEntity, AuthoringScene, AuthoringSession


@dataclass(frozen=True, slots=True)
class ScriptRunResult:
    success: bool
    stdout: str = ""
    error: str = ""
    filename: str = ""
    line: int | None = None
    column: int | None = None
    exception_type: str = ""

    @property
    def diagnostic(self):
        if self.success:
            return ""
        location = ""
        if self.line is not None:
            location = f"{self.filename}:{self.line}"
            if self.column is not None:
                location += f":{self.column}"
            location += "\n"
        return f"{location}{self.error}"


def _diagnostic_for_exception(exc, filename):
    line = None
    column = None
    if isinstance(exc, SyntaxError):
        line = exc.lineno
        column = exc.offset
    else:
        tb = traceback.extract_tb(exc.__traceback__)
        matching = [frame for frame in tb if frame.filename == filename]
        frame = matching[-1] if matching else (tb[-1] if tb else None)
        if frame is not None:
            line = frame.lineno
    return line, column


def run_authoring_script(
    source,
    project,
    *,
    execute=None,
    filename="<asteria-script>",
    selection_kind="none",
    selection_value=None,
):
    """Run trusted local project Python against the Authoring API.

    Convenience globals:
    - project: AuthoringSession
    - selected: current Editor selection wrapped by the Authoring API, if any
    - scene: selected Scene, or selected Entity's owning Scene, if available
    - entity: selected Entity, if available

    This is deliberately not a security sandbox.
    """
    session = AuthoringSession(project, execute=execute)
    selected = session.wrap_selection(selection_kind, selection_value)

    scene = None
    entity = None
    if isinstance(selected, AuthoringScene):
        scene = selected
    elif isinstance(selected, AuthoringEntity):
        entity = selected
        scene = selected._scene

    output = io.StringIO()
    namespace = {
        "__name__": "__asteria_authoring__",
        "__file__": filename,
        "project": session,
        "selected": selected,
        "scene": scene,
        "entity": entity,
    }

    try:
        code = compile(str(source), filename, "exec")
        with contextlib.redirect_stdout(output):
            # This boundary intentionally executes a project authoring script.
            exec(code, namespace, namespace)  # noqa: S102
        return ScriptRunResult(
            True,
            stdout=output.getvalue(),
            filename=filename,
        )
    except Exception as exc:  # noqa: BLE001
        # Script failures are returned as diagnostics instead of crashing the editor.
        line, column = _diagnostic_for_exception(exc, filename)
        return ScriptRunResult(
            False,
            stdout=output.getvalue(),
            error=traceback.format_exc(),
            filename=filename,
            line=line,
            column=column,
            exception_type=type(exc).__name__,
        )
