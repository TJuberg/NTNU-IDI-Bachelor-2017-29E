FROM base/archlinux

# Set the $architecture ARG on your `docker build' command line with `--build-arg architecture=x86_64' or `i686'.

RUN pacman-key --init \
    && pacman-key --populate archlinux \
    && pacman -Syy --noconfirm --noprogressbar --quiet \
    # Download all packages before proceeding to work around issue with ca-certificates package
    && pacman -Syuw --noconfirm --noprogressbar --quiet\
    && rm -f /etc/ssl/certs/ca-certificates.crt \   
    && pacman -Su --noconfirm --noprogressbar --quiet \
    # Unfortunately this hack has to stay until Arch Linux bootstrap tarballs start including `sed' package, which is
    # required by `rankmirrors', which comes with `pacman' package, while that one doesn't depend on `sed'. (Note to
    # self: ask the Arch devs about this; `locale-gen' uses `sed' too).
    && pacman -S --noconfirm --noprogressbar --quiet sed vim\
    # `locale-gen' needs `gzip' (via `localedef', which works on /usr/share/i18n/charmaps/*.gz), `paccache' needs `awk'.
    && pacman -S --noconfirm --noprogressbar --quiet gzip awk base openssh \
    && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && paccache -r -k0 \
    && echo 'en_US.UTF-8 UTF-8' > /etc/locale.gen \
    && locale-gen \
    && echo 'LANG=en_US.UTF-8' > /etc/locale.conf \
    && ssh-keygen -A 
RUN echo 'root:vagrant' | chpasswd


RUN pacman -S --noconfirm --noprogressbar --quiet --needed base-devel python python2 \
    python-pip python2-pip git zsh tmux python2-crypto python2-paramiko python2-yaml \
    python2-jinja

RUN cp /etc/skel/.bash_profile /root/
RUN cp /etc/skel/.bashrc /root/

RUN echo "if [ -f ~/.bash_aliases ]; then" >> /root/.bashrc
RUN echo "    . ~/.bash_aliases" >> /root/.bashrc
RUN echo "fi" >> /root/.bashrc

RUN echo "source /opt/ansible/hacking/env-setup -q" >> /root/.bashrc                                           
RUN echo "export ANSIBLE_VAULT_PASSWORD_FILE=~/bachelor/.vaultsecret" >> /root/.bashrc  
RUN echo "alias ap='ansible-playbook'" >> /root/.bash_aliases
RUN echo "alias a='ansible'" >> /root/.bash_aliases
                                                       
RUN pip2 install -U junos-eznc junos-netconify ncclient pysnmp

RUN git clone https://github.com/ansible/ansible.git /opt/ansible
RUN git --git-dir=/opt/ansible/.git --work-tree=/opt/ansible checkout stable-2.3

EXPOSE 22

CMD ["/usr/sbin/sshd", "-D"]  
ENV LANG en_US.UTF-8

# As per https://docs.docker.com/engine/userguide/networking/default_network/configure-dns/, the /etc/hostname,
# /etc/hosts and /etc/resolv.conf should be rather left alone.
