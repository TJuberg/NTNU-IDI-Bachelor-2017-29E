FROM ubuntu:16.04

RUN apt update \
    && DEBIAN_FRONTEND=noninteractive apt -y -q install iputils-ping environment-modules echolot tmux \
    openssh-client openssh-server zsh git build-essential python python-certifi wget \
    libssl-dev python-dev python3-dev python-cffi python3-cffi python-setuptools python3-setuptools vim nano dnsutils

RUN wget -nv https://bootstrap.pypa.io/get-pip.py
RUN python2 get-pip.py
RUN pip2 install -U jinja2 PyYAML paramiko pycrypto junos-eznc junos-netconify ncclient pysnmp
#RUN pip3 install -U jinja2 PyYAML paramiko pycrypto junos-eznc junos-netconify ncclient pysnmp

RUN echo 'root:vagrant' | chpasswd 
RUN sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd
ENV NOTVISIBLE "in users profile"
RUN echo "export VISIBLE=now" >> /etc/profile
RUN mkdir /var/run/sshd
EXPOSE 22


RUN echo "source /opt/ansible/hacking/env-setup -q" >> /root/.bashrc
RUN echo "export ANSIBLE_VAULT_PASSWORD_FILE=~/bachelor/.vaultsecret" >> /root/.bashrc
RUN echo "alias ap='ansible-playbook'" >> /root/.bash_aliases
RUN echo "alias a='ansible'" >> /root/.bash_aliases

RUN git clone https://github.com/ansible/ansible.git /opt/ansible
RUN git --git-dir=/opt/ansible/.git --work-tree=/opt/ansible checkout stable-2.3

CMD ["/usr/sbin/sshd", "-D","-d"]

