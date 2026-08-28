# WHO BROKE THE RACK
# Server #4 Rocky Linux 9.8 Bare-Metal Provisioning

lang ko_KR.UTF-8
keyboard --vckeymap=kr
timezone Asia/Seoul --utc

url --url="http://192.168.100.60:8080/rocky9-repo"

network --bootproto=dhcp --device=70:10:6f:a1:aa:41 --activate --hostname=dca-spare01

rootpw --lock x
user --name=rocky --groups=wheel --password=<REPLACE_WITH_SHA512_PASSWORD_HASH> --iscrypted

selinux --enforcing
firewall --enabled --service=ssh
firstboot --disable

ignoredisk --only-use=sda
zerombr
clearpart --all --initlabel --drives=sda
autopart --type=lvm
bootloader --location=mbr --boot-drive=sda

%packages
@^minimal-environment
openssh-server
sudo
%end

%post
systemctl enable sshd
%end

reboot
