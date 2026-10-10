FROM kalilinux/kali-rolling

# Installation des outils nécessaires
RUN apt-get update && \
     apt-get install -y --no-install-recommends \
     python3 \
     openssh-server \
     netcat-openbsd \
     curl \
     ca-certificates \
     passwd && \
     apt-get clean && \
     rm -rf /var/lib/apt/lists/*

# Configuration SSH
RUN mkdir -p /var/run/sshd && \
     echo 'root:kali' | chpasswd && \
     printf '\nPermitRootLogin yes\nPasswordAuthentication yes\n' \
     >> /etc/ssh/sshd_config

WORKDIR /tmp

EXPOSE 22 80

# SSH au premier plan et serveur HTTP en arrière-plan
CMD ["sh", "-c", "python3 -m http.server 80 & exec /usr/sbin/sshd -D -e"]