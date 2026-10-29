# A clean Linux machine for the test suite (scripts/docker_tests.sh). The image holds only
# Python, the system libraries Qt and SDL need, and the packages pyproject.toml asks for;
# the project's files come in when the tests run, so a rebuild is needed only when the
# dependencies change.
ARG PYTHON=3.13
FROM python:${PYTHON}-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libdbus-1-3 libfontconfig1 \
        libglib2.0-0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 \
        libxcb-xkb1 libxrender1 libsdl2-2.0-0 g++ \
    && rm -rf /var/lib/apt/lists/*

ENV SDL_VIDEODRIVER=dummy \
    SDL_AUDIODRIVER=dummy \
    QT_QPA_PLATFORM=offscreen \
    ASTERIA_MUTE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# the extras the suite needs, read from pyproject.toml; PINS fixes versions to try another
# one (e.g. PINS="PySide6==6.11.2")
ARG EXTRAS="pygame editor mv dev"
ARG PINS=""
COPY pyproject.toml /deps/pyproject.toml
RUN python -c "import tomllib, sys; extras = tomllib.load(open('/deps/pyproject.toml', 'rb'))['project']['optional-dependencies']; print('\n'.join(sorted({d for name in sys.argv[1:] for d in extras[name]})))" ${EXTRAS} > /deps/requirements.txt \
    && pip install --no-cache-dir -r /deps/requirements.txt ${PINS}

WORKDIR /work
