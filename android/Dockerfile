FROM docker.io/ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=$ANDROID_HOME
ENV PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools
ENV DISPLAY=:99
ENV USERNAME=androiduser
ENV HOME=/home/$USERNAME

SHELL ["/bin/bash", "-lc"]

RUN sed -i 's|http://archive.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list && \
    sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' /etc/apt/sources.list && \
    apt-get update && apt-get -y upgrade && \
    apt-get install -y \
        wget unzip curl git sudo python3-pip openjdk-17-jdk \
        build-essential \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        libssl-dev \
        libffi-dev \
        libncurses5-dev \
        libncursesw5-dev \
        zlib1g-dev \
        xz-utils \
        tk-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash -d $HOME $USERNAME && \
    echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
USER $USERNAME
WORKDIR $HOME

USER root
RUN mkdir -p $ANDROID_SDK_ROOT/cmdline-tools && \
    chmod -R 777 $ANDROID_SDK_ROOT && \
    curl -o /tmp/cmdline-tools.zip https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip && \
    unzip /tmp/cmdline-tools.zip -d $ANDROID_SDK_ROOT/cmdline-tools && \
    mv $ANDROID_SDK_ROOT/cmdline-tools/cmdline-tools $ANDROID_SDK_ROOT/cmdline-tools/latest && \
    rm /tmp/cmdline-tools.zip
USER $USERNAME

RUN yes | sdkmanager --licenses || true && \
    sdkmanager "platform-tools"

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

COPY --chown=$USERNAME:$USERNAME . $HOME

USER root
COPY android/start.sh /opt/start.sh
RUN chmod +x /opt/start.sh
USER $USERNAME

EXPOSE 6080 5555

ENTRYPOINT ["/opt/start.sh"]

# docker build -t android-agent -f android/Dockerfile .
# docker run -it --rm -p 6080:6080 android-agent --agents default_agent_mobile --task_file "task_file.json"
# docker system prune -a --volumes