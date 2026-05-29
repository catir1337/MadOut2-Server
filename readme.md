# Auth+Game Server for MadOut2

Auth server → `main.py`  
Game server → `MadOut2.exe bend_GameServer -batchmode -port:<port> `

*Версия Server урезанная, чтобы работал лишь сервер в режиме -batchmode* 
---

### Добавление сервера в `main.py`

```json
{"ip": "ip gameserver", "port": 7800, "name": "Сервер Навального", "players": 0, "maxPlayers": 100}
```

### `config.ini` рядом с `MadOut2.exe`

```ini
server_ip=127.0.0.1
bend_port=35000
```

---
[TELGRAM MDMP](https://t.me/mdmp1337)
[Video Proof YouTube](https://youtu.be/GgpAtbjKmzU)  
*By catir1337*
