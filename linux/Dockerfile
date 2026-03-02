# Default to a mainland China-friendly mirror; override with --build-arg UBUNTU_IMAGE=...
ARG UBUNTU_IMAGE=docker.m.daocloud.io/library/ubuntu:22.04
FROM ${UBUNTU_IMAGE} AS desktop-base

ENV DEBIAN_FRONTEND=noninteractive
ENV DEBIAN_PRIORITY=high

SHELL ["/bin/bash", "-lc"]

# Base system dependencies (no repo files copied yet, so this layer stays cached)
RUN apt-get update && \
    apt-get -y upgrade && \
    apt-get install -y \
        xvfb xterm xdotool scrot gnome-screenshot imagemagick sudo mutter x11vnc xfce4 xfce4-terminal \
        build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
        libsqlite3-dev curl git libncursesw5-dev xz-utils tk-dev libxml2-dev \
        libxmlsec1-dev libffi-dev liblzma-dev net-tools netcat software-properties-common \
        chromium-browser \
        libgl1-mesa-dri libgl1-mesa-glx mesa-utils libglu1-mesa libosmesa6 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install arm64 geckodriver (Firefox) for selenium fallback
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then \
      GECKO_VER=v0.35.0 && \
      curl -fsSL -o /tmp/geckodriver.tar.gz "https://github.com/mozilla/geckodriver/releases/download/${GECKO_VER}/geckodriver-${GECKO_VER}-linux-aarch64.tar.gz" && \
      tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin && \
      rm /tmp/geckodriver.tar.gz; \
    else \
      echo "Skipping geckodriver download for arch $ARCH"; \
    fi

RUN add-apt-repository -y ppa:mozillateam/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        firefox-esr libreoffice x11-apps xpdf gedit xpaint tint2 galculator pcmanfm unzip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# noVNC + websockify
RUN git clone --branch v1.5.0 https://github.com/novnc/noVNC.git /opt/noVNC && \
    git clone --branch v0.12.0 https://github.com/novnc/websockify /opt/noVNC/utils/websockify && \
    ln -s /opt/noVNC/vnc.html /opt/noVNC/index.html

# Create runtime user
ENV USERNAME=computeruse
ENV HOME=/home/$USERNAME

RUN useradd -m -s /bin/bash -d $HOME $USERNAME && \
    echo "computeruse:1" | chpasswd && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

USER computeruse
WORKDIR $HOME

# pyenv setup (done once in the base stage)
ENV PYENV_ROOT=$HOME/.pyenv
ENV PATH=$PYENV_ROOT/bin:$PATH

RUN if [ ! -d "$PYENV_ROOT" ]; then git clone https://github.com/pyenv/pyenv.git $PYENV_ROOT; fi

RUN $PYENV_ROOT/bin/pyenv install --skip-existing 3.10.18 && \
    $PYENV_ROOT/bin/pyenv install --skip-existing 3.11.13 && \
    $PYENV_ROOT/bin/pyenv install --skip-existing 3.12.11 && \
    $PYENV_ROOT/bin/pyenv global 3.12.11

RUN for ver in 3.10.18 3.11.13 3.12.11; do \
        $PYENV_ROOT/versions/$ver/bin/python -m ensurepip && \
        $PYENV_ROOT/versions/$ver/bin/python -m pip install --upgrade pip setuptools wheel uv; \
    done

RUN echo 'export PYENV_ROOT="$HOME/.pyenv"' >> $HOME/.bashrc && \
    echo 'export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"' >> $HOME/.bashrc && \
    echo 'eval "$(pyenv init --path)"' >> $HOME/.bashrc && \
    echo 'eval "$(pyenv init -)"' >> $HOME/.bashrc

USER root
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix
USER computeruse
RUN touch $HOME/.Xauthority

# ---------------- Final runtime stage ----------------
FROM desktop-base

ENV USERNAME=computeruse
ENV HOME=/home/$USERNAME
ENV PYENV_ROOT=$HOME/.pyenv
ENV PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
ENV LIBGL_ALWAYS_SOFTWARE=1
ENV MESA_GL_VERSION_OVERRIDE=4.5
WORKDIR $HOME

COPY --chown=$USERNAME:$USERNAME . $HOME

ENV DISPLAY=:99

# Pre-install anthropic_agent venv to avoid runtime package downloads
RUN export PYENV_ROOT="$HOME/.pyenv" PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH" && \
    eval "$(pyenv init -)" && \
    pyenv shell 3.11.13 && \
    mkdir -p .venvs && \
    python -m venv .venvs/anthropic_agent && \
    .venvs/anthropic_agent/bin/pip install --upgrade pip setuptools wheel -i https://pypi.tuna.tsinghua.edu.cn/simple --extra-index-url https://pypi.org/simple && \
    .venvs/anthropic_agent/bin/pip install --no-cache-dir -r agents/anthropic_agent/requirements.txt \
        -i https://pypi.tuna.tsinghua.edu.cn/simple --extra-index-url https://pypi.org/simple && \
    .venvs/anthropic_agent/bin/pip list

USER root
COPY linux/start.sh /opt/start.sh
RUN chmod +x /opt/start.sh && mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix
USER computeruse

ENTRYPOINT ["/opt/start.sh"]

# docker build -t desktop-agent -f linux/Dockerfile .
# docker run -it --rm -p 6080:6080 desktop-agent --agents web_voyager_agent
