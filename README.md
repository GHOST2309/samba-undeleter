# samba-undeleter
Samba's recycle bin remote management. Server (mover) and client (requester). Utilizes `recycle` and `full_audit` vfs modules.
## Installation
Configure the share
```
[public]
vfs objects = recycle full_audit
full_audit: prefix  = %u|%M|%I|%P
full_audit: success = rewinddir renameat unlinkat
```
Install the server
```
mv undeleter.py /usr/local/bin/undeleter.py
chmod 755 /usr/local/bin/undeleter.py
chown root:root /usr/local/bin/undeleter.py
```
Install and enable the service
```
mv undeleter.service /etc/systemd/system/undeleter.service
systemctl enable undeleter.service
systemctl start undeleter.service
```
Install and load AppArmor profile
```
mv etc/apparmor.d/undeleter /etc/apparmor.d/undeleter
apparmor_parser --add /etc/apparmor.d/undeleter
```
