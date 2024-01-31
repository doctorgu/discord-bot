# Ubuntu

## [/lib/systemd/system/discord-bot.service]

```config
[Unit]
Description=discord-bot
After=network-online.target

[Service]
Restart=on-failure
WorkingDirectory=/root/discord-bot/
ExecStart=/usr/bin/python3 /root/discord-bot/discord-bot.py schedule-bot

[Install]
WantedBy=multi-user.target
```

## cmd

```cmd
systemctl daemon-reload
systemctl enable discord-bot.service
systemctl disable discord-bot.service

systemctl start discord-bot.service
systemctl restart discord-bot.service
systemctl stop discord-bot.service
systemctl status discord-bot.service
```
