# Edge Server Audit — k2-MotherBoard-Series — 2026-07-26T02:01:38-07:00

## 0. GPU — the Phase 0 gate

```
01:00.0 VGA compatible controller [0300]: NVIDIA Corporation GP106 [GeForce GTX 1060 3GB] [10de:1c02] (rev a1)
01:00.1 Audio device [0403]: NVIDIA Corporation GP106 High Definition Audio Controller [10de:10f1] (rev a1)
05:00.0 VGA compatible controller [0300]: Advanced Micro Devices, Inc. [AMD/ATI] Raphael [1002:164e] (rev d8)
--- loaded kernel driver:
nouveau              3178496  26
--- nvidia-smi:
nvidia-smi NOT FOUND -> proprietary driver not installed (Phase 0 incomplete)
```

## 1. Hardware & OS

```
CPU:    AMD Ryzen 9 7945HX with Radeon Graphics
Cores:  32 threads
               total        used        free      shared  buff/cache   available
Mem:            59Gi        10Gi        36Gi       784Mi        13Gi        48Gi
Swap:          8.0Gi       640Ki       8.0Gi
---
OS: Ubuntu 26.04 LTS
7.0.0-28-generic
 02:01:38 up  2:04,  1 user,  load average: 0.94, 0.99, 0.87
```

## 2. Storage

```
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p2  915G  206G  664G  24% /
efivarfs        128K   54K   70K  44% /sys/firmware/efi/efivars
/dev/nvme0n1p1  1.1G  6.4M  1.1G   1% /boot/efi
/dev/sda2       7.3T  154G  7.2T   3% /mnt/tick-storage
--- largest directories under / (top 10):
87G	/
56G	/home
16G	/var
6.9G	/usr
415M	/opt
136M	/boot
12M	/etc
148K	/snap
16K	/lost+found
12K	/media
--- docker disk usage:
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          29        19        71.51GB   63.72GB (89%)
Containers      22        2         33.61GB   33.61GB (99%)
Local Volumes   3         3         1.007GB   0B (0%)
Build Cache     12        0         12.22GB   5.898MB
```

## 3. Thermals & power

```
lm-sensors not installed (apt install lm-sensors && sensors-detect)
```

## 4. Docker state

```
Docker version 29.1.3, build 29.1.3-0ubuntu4.1
--- networks:
NETWORK ID     NAME                     DRIVER    SCOPE
71e09de811fd   bridge                   bridge    local
59c63c037c39   host                     host      local
73127237d4bb   hx_default               bridge    local
c18f1e9ac65e   local-network            bridge    local
63ba12555812   none                     null      local
1610fa43cc20   ut-bot-lumibot_default   bridge    local
--- running containers (name, image, ports, restart policy):
NAMES                      IMAGE                    PORTS                                                                                                                                   STATUS
ut-bot-lumibot-questdb-1   questdb/questdb:latest   0.0.0.0:8812->8812/tcp, [::]:8812->8812/tcp, 0.0.0.0:9000->9000/tcp, [::]:9000->9000/tcp, 0.0.0.0:9009->9009/tcp, [::]:9009->9009/tcp   Up 2 hours
ut-bot-lumibot-qdrant-1    qdrant/qdrant:latest     0.0.0.0:6333->6333/tcp, [::]:6333->6333/tcp, 6334/tcp                                                                                   Up 2 hours
--- containers with host-published ports (exposure surface):
ut-bot-lumibot-questdb-1	0.0.0.0:8812->8812/tcp, [::]:8812->8812/tcp, 0.0.0.0:9000->9000/tcp, [::]:9000->9000/tcp, 0.0.0.0:9009->9009/tcp, [::]:9009->9009/tcp
ut-bot-lumibot-qdrant-1	0.0.0.0:6333->6333/tcp, [::]:6333->6333/tcp, 6334/tcp
--- memory limits per running container:
/ut-bot-lumibot-questdb-1      NO LIMIT
/ut-bot-lumibot-qdrant-1       NO LIMIT
--- nvidia runtime configured:
nvidia runtime NOT in docker info
```

## 5. Network exposure

```
--- listening sockets (host):
Netid State  Recv-Q Send-Q                               Local Address:Port  Peer Address:PortProcess                                 
udp   UNCONN 0      0                                          0.0.0.0:1901       0.0.0.0:*                                           
udp   UNCONN 0      0                                       172.17.0.1:35475      0.0.0.0:*                                           
udp   UNCONN 0      0                                       172.18.0.1:3702       0.0.0.0:*    users:(("python3",pid=25398,fd=22))    
udp   UNCONN 0      0                                  239.255.255.250:3702       0.0.0.0:*    users:(("python3",pid=25398,fd=20))    
udp   UNCONN 0      0                                       172.20.0.1:3702       0.0.0.0:*    users:(("python3",pid=25398,fd=19))    
udp   UNCONN 0      0                                  239.255.255.250:3702       0.0.0.0:*    users:(("python3",pid=25398,fd=17))    
udp   UNCONN 0      0                                       172.19.0.1:3702       0.0.0.0:*    users:(("python3",pid=25398,fd=16))    
udp   UNCONN 0      0                                  239.255.255.250:3702       0.0.0.0:*    users:(("python3",pid=25398,fd=14))    
udp   UNCONN 0      0                                       172.17.0.1:3702       0.0.0.0:*    users:(("python3",pid=25398,fd=13))    
udp   UNCONN 0      0                                  239.255.255.250:3702       0.0.0.0:*    users:(("python3",pid=25398,fd=11))    
udp   UNCONN 0      0                                   192.168.29.169:3702       0.0.0.0:*    users:(("python3",pid=25398,fd=10))    
udp   UNCONN 0      0                                  239.255.255.250:3702       0.0.0.0:*    users:(("python3",pid=25398,fd=8))     
udp   UNCONN 0      0                                       172.19.0.1:37013      0.0.0.0:*                                           
udp   UNCONN 0      0                                          0.0.0.0:37509      0.0.0.0:*    users:(("python3",pid=25398,fd=21))    
udp   UNCONN 0      0                                          0.0.0.0:5353       0.0.0.0:*                                           
udp   UNCONN 0      0                                       172.18.0.1:40057      0.0.0.0:*                                           
udp   UNCONN 0      0                                          0.0.0.0:40474      0.0.0.0:*    users:(("rustdesk",pid=227560,fd=18))  
udp   UNCONN 0      0                                          0.0.0.0:41370      0.0.0.0:*    users:(("python3",pid=25398,fd=15))    
udp   UNCONN 0      0                                        127.0.0.1:42784      0.0.0.0:*                                           
udp   UNCONN 0      0                                       172.19.0.1:47826      0.0.0.0:*                                           
udp   UNCONN 0      0                                       172.20.0.1:51439      0.0.0.0:*                                           
udp   UNCONN 0      0                                        127.0.0.1:51533      0.0.0.0:*                                           
udp   UNCONN 0      0                                       172.19.0.1:51591      0.0.0.0:*                                           
udp   UNCONN 0      0                                   192.168.29.169:52522      0.0.0.0:*                                           
udp   UNCONN 0      0                                          0.0.0.0:21119      0.0.0.0:*    users:(("rustdesk",pid=227560,fd=3567))
udp   UNCONN 0      0                                       172.20.0.1:55002      0.0.0.0:*                                           
udp   UNCONN 0      0                                       172.18.0.1:55195      0.0.0.0:*                                           
udp   UNCONN 0      0                                   192.168.29.169:55421      0.0.0.0:*                                           
udp   UNCONN 0      0                                       172.17.0.1:56520      0.0.0.0:*                                           
udp   UNCONN 0      0                                          0.0.0.0:56682      0.0.0.0:*    users:(("python3",pid=25398,fd=9))     
udp   UNCONN 0      0                                          0.0.0.0:57223      0.0.0.0:*    users:(("python3",pid=25398,fd=18))    
udp   UNCONN 0      0                                       172.18.0.1:57552      0.0.0.0:*                                           
udp   UNCONN 0      0                                       172.20.0.1:59143      0.0.0.0:*                                           
udp   UNCONN 0      0                                       172.17.0.1:59709      0.0.0.0:*                                           
udp   UNCONN 0      0                                          0.0.0.0:32410      0.0.0.0:*                                           
udp   UNCONN 0      0                                          0.0.0.0:32412      0.0.0.0:*                                           
udp   UNCONN 0      0                                          0.0.0.0:32413      0.0.0.0:*                                           
udp   UNCONN 0      0                                          0.0.0.0:32414      0.0.0.0:*                                           
udp   UNCONN 0      0                                       127.0.0.54:53         0.0.0.0:*                                           
--- firewall:
ufw status needs sudo
--- tailscale:
tailscale not installed
```

## 6. Security posture (basic)

```
--- ssh daemon:
sshd_config not readable without sudo
--- docker socket group members (can root the box):
docker:x:122:k2
--- pending security updates:
0 security updates pending
--- possible plaintext secrets in compose files under /opt (filenames only):
no /opt/home-edge compose files found (or clean)
```

## 7. Backups & data layout

```
MISSING: /opt/home-edge
MISSING: /opt/home-edge-data
MISSING: /opt/home-edge-backups
--- newest backup artifact:
no backups found
--- systemd timers (backup/prune):
Mon 2026-07-27 00:00:00 MST      21h Sun 2026-07-26 00:00:00 MST  2h 1min ago dpkg-db-backup.timer           dpkg-db-backup.service
```

## Done. Paste this whole report back for severity-tiered analysis.
