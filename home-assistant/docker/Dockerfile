ARG version

FROM homeassistant/home-assistant:$version

# Compile an up-to-date FFMpeg:
RUN apt-get update \
      && apt-get install -y \
        autoconf \
        automake \
        build-essential \
        cmake \
        git-core \
        libass-dev \
        libfreetype6-dev \
        libnuma-dev \
        libnuma-dev \
        libsdl2-dev \
        libtool \
        libva-dev \
        libvdpau-dev \
        libvorbis-dev \
        libvpx-dev \
        libx264-dev \
        libx265-dev \
        libxcb-shm0-dev \
        libxcb-xfixes0-dev \
        libxcb1-dev \
        mercurial \
        pkg-config \
        texinfo \
        wget \
        yasm \
        zlib1g-dev \
      && mkdir ffmpeg_build \
      && mkdir ffmpeg_sources \
      && cd ffmpeg_sources \
      && wget -O ffmpeg-snapshot.tar.bz2 https://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2 \
      && tar xjvf ffmpeg-snapshot.tar.bz2 \
      && cd ffmpeg \
      && PKG_CONFIG_PATH="/usr/src/app/ffmpeg_build/lib/pkgconfig" ./configure \
        --prefix="/usr/src/app/ffmpeg_build" \
        --pkg-config-flags="--static" \
        --extra-cflags="-I/usr/src/app/ffmpeg_build/include" \
        --extra-ldflags="-L/usr/src/app/ffmpeg_build/lib" \
        --extra-libs="-lpthread -lm" \
        --bindir="/usr/local/bin" \
        --enable-gpl \
        --enable-libass \
        --enable-libfreetype \
        --enable-libvorbis \
        --enable-libvpx \
        --enable-libx264 \
        --enable-libx265 \
        --enable-nonfree \
      && make \
      && make install \
      && hash -r \
      && apt-get remove -y \
        autoconf \
        automake \
        build-essential \
        cmake \
        git-core \
        libass-dev \
        libfreetype6-dev \
        libnuma-dev \
        libnuma-dev \
        libsdl2-dev \
        libtool \
        libva-dev \
        libvdpau-dev \
        libvorbis-dev \
        libvpx-dev \
        libx264-dev \
        libx265-dev \
        libxcb-shm0-dev \
        libxcb-xfixes0-dev \
        libxcb1-dev \
        mercurial \
        pkg-config \
        texinfo \
        wget \
        yasm \
        zlib1g-dev \
      && apt-get clean \
      && rm -rf /var/lib/apt/lists/*
