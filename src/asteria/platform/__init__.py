from asteria.platform.backend import RuntimeBackend
from asteria.platform.headless_backend import HeadlessBackend

try:
    from asteria.platform.pygame_backend import PygameRuntimeBackend, PygameTextureBackend
except ImportError:
    PygameRuntimeBackend = None
    PygameTextureBackend = None

from asteria.platform.pygame_battle_ui import PygameBattleUiBackend
