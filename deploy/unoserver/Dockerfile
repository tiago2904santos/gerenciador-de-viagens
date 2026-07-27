FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-writer \
        python3 \
        python3-pip \
        python3-uno \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages --no-cache-dir "unoserver>=3.4,<4.0"

RUN useradd --create-home --uid 10001 documentos
COPY start-unoserver.sh /usr/local/bin/start-unoserver
COPY warmup.rtf /opt/unoserver/warmup.rtf
RUN chmod 0755 /usr/local/bin/start-unoserver
USER documentos
WORKDIR /home/documentos

EXPOSE 2003
CMD ["/usr/local/bin/start-unoserver"]
