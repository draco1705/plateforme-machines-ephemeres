FROM kalilinux/kali-rolling

# Installer les outils nécessaires
RUN apt-get clean && \
     rm -rf /var/lib/apt/lists/* && \
     apt-get update && \
     apt-get upgrade -y && \
     apt-get install -y --no-install-recommends \
     python3 \
     openssh-server \
     netcat-openbsd \
     curl \
     ca-certificates && \
     apt-get clean && \
     rm -rf /var/lib/apt/lists/*

# Configuration SSH
RUN mkdir -p /var/run/sshd && \
     echo 'root:kali' | chpasswd && \
     sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
     sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

WORKDIR /tmp

EXPOSE 22 80

CMD ["sh", "-c", "python3 -m http.server 80 & exec /usr/sbin/sshd -D"]
