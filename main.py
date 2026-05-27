import socket, struct, threading, time, json, uuid, random, string

PORT     = 35000
SECRET   = "uuuttt_hello_world_123"
DEBUG    = True

SERVERS = [
     {"ip":"127.0.0.1","port":7800,"name":"Сервер Навального","players":0,"maxPlayers":100}
]


PROP_UNRELIABLE       = 0
PROP_CHANNELED        = 1
PROP_ACK              = 2
PROP_PING             = 3
PROP_PONG             = 4
PROP_CONNECT_REQUEST  = 5
PROP_CONNECT_ACCEPT   = 6
PROP_DISCONNECT       = 7

REQ_MAGIC  = 22000   
RESP_MAGIC = 15777   

R='\033[91m'; G='\033[92m'; Y='\033[93m'; C='\033[96m'; W='\033[0m'
def log(m, c=W): print(f"{c}{m}{W}", flush=True)


class Reader:
    def __init__(self, d, offset=0): self.d=d; self.pos=offset
    def byte(self):
        v=self.d[self.pos]; self.pos+=1; return v
    def short(self):
        v=struct.unpack_from('<h',self.d,self.pos)[0]; self.pos+=2; return v
    def ushort(self):
        v=struct.unpack_from('<H',self.d,self.pos)[0]; self.pos+=2; return v
    def int32(self):
        v=struct.unpack_from('<i',self.d,self.pos)[0]; self.pos+=4; return v
    def uint32(self):
        v=struct.unpack_from('<I',self.d,self.pos)[0]; self.pos+=4; return v
    def int64(self):
        v=struct.unpack_from('<q',self.d,self.pos)[0]; self.pos+=8; return v
    def string_i32(self):
        l=self.int32()
        if l<=0: return ""
        s=self.d[self.pos:self.pos+l].decode('utf-8','replace'); self.pos+=l; return s
    def available(self): return len(self.d)-self.pos

class Writer:
    def __init__(self): self.buf=bytearray()
    def byte(self,v):   self.buf+=struct.pack('B',v&0xFF)
    def short(self,v):  self.buf+=struct.pack('<h',v)
    def ushort(self,v): self.buf+=struct.pack('<H',v&0xFFFF)
    def int32(self,v):  self.buf+=struct.pack('<i',v)
    def uint32(self,v): self.buf+=struct.pack('<I',v)
    def int64(self,v):  self.buf+=struct.pack('<q',v)
    def raw(self,b):    self.buf+=b
    def string_i32(self,s):
        if not s: self.int32(0); return
        b=s.encode('utf-8'); self.int32(len(b)); self.buf+=b
    def bytes(self):    return bytes(self.buf)



def get_conn_num(prop_byte):
    return (prop_byte & 0x60) >> 5

def send_connect_accept(sock, addr, connect_time, conn_num):
    w=Writer()
    w.byte(PROP_CONNECT_ACCEPT)  # [0] = 6
    w.int64(connect_time)         # [1-8]
    w.byte(conn_num)              # [9] connectionNumber
    w.byte(0)                     # [10] isReusedPeer = false
    sock.sendto(w.bytes(), addr)

def send_ack(sock, addr, channel_id, seq, conn_num):
    bitmask = bytearray(9)
    idx = seq % 64
    bitmask[idx // 8] |= (1 << (idx % 8))
    pkt = bytearray(13)
    pkt[0] = PROP_ACK | (conn_num << 5)
    struct.pack_into('<H', pkt, 1, seq)
    pkt[3] = channel_id
    pkt[4:13] = bitmask
    sock.sendto(bytes(pkt), addr)

def send_unreliable(sock, addr, payload):
    sock.sendto(bytes([PROP_UNRELIABLE]) + payload, addr)

def make_resp(index, is_error, result):
    w=Writer()
    w.short(RESP_MAGIC)      # short → 2 bytes
    w.uint32(index)           # uint → 4 bytes
    w.short(is_error)         # short → 2 bytes
    w.string_i32(result)     # int32 len + bytes
    return w.bytes()


tokens={}; users={}; next_uid=[1]

def create_user():
    uid=next_uid[0]; next_uid[0]+=1
    login=f"user_{random.randint(100000,999999)}"
    pwd=''.join(random.choices(string.ascii_letters+string.digits,k=10))
    users[uid]={"login":login,"pass":pwd,"nick":f"Player{uid}","ab":0}
    return uid,login,pwd

def find_user(login,pwd):
    for uid,u in users.items():
        if u["login"]==login and u["pass"]==pwd: return uid
    return None


def handle(url, body, addr):
    log(f"    → {url}", C)
    try:
        data=json.loads(body) if body and body.strip().startswith('{') else {}
    except: data={}

    if url in ("/mirror/hand_shake/","/main/hand_shake/"):
        return json.dumps({"hand_shake_guid":uuid.uuid4().hex})

    if url=="/main/get_token/":
        token=uuid.uuid4().hex; tokens[token]=None
        log(f"    token → {token[:8]}...", G)
        return json.dumps({"token":token})

    if url=="/main/register/":
        token=data.get("token","")
        uid,login,pwd=create_user(); tokens[token]=uid
        log(f"    register → uid={uid}", G)
        return json.dumps({"login":login,"pass":pwd})

    if url=="/main/login/":
        token=data.get("token","")
        login=data.get("login",""); pwd=data.get("pass","")
        uid=find_user(login,pwd)
        if uid is None:
            uid,_,_=create_user()
            users[uid]["login"]=login; users[uid]["pass"]=pwd
        tokens[token]=uid; u=users[uid]
        log(f"    login → uid={uid} nick={u['nick']}", G)
        return json.dumps({"ID":uid,"nick":u["nick"],"ab":u["ab"],"settings":{}})

    if url=="/main/check_state/":
        return json.dumps({})

    if url=="/stat/session_begin/":
        return json.dumps({"hard_id":1,"hard_uid":uuid.uuid4().hex})

    if url=="/stat/data/":
        return json.dumps({})

    if url=="/match/list/":
        items=[{
            "serverGUID":     str(uuid.uuid4()),
            "ip":             s["ip"],
            "port":           s["port"],
            "playerCount":    s.get("players",0),
            "connectsCount":  0,
            "playersMaxCount":s.get("maxPlayers",50),
            "connState":      0,
            "lang":           "ru",
            "playModeGroup":  "FreeRoam",
            "playModeDesc":   s.get("name","Server"),
            "isCanConnect":   True,
        } for s in SERVERS]
        log(f"    /match/list/ → {len(SERVERS)} серверов", G)
        return json.dumps({"Items":items})

    if url=="/match/try_connect_to_game_server/":
        if not SERVERS:
            log("    [!] Нет серверов — добавь в SERVERS", Y)
            return "fail_because_busy"
        s=SERVERS[0]
        return json.dumps({"ip":s["ip"],"port":s["port"]})

    if url=="/system/check_connect":
        return body

    log(f"    [404] {url}", Y)
    return json.dumps({"error":f"404: {url}"})



def on_connect_request(sock, addr, data):
    connect_time=int(time.time()*1000)
    version=0; secret=""
    conn_num = get_conn_num(data[0])

    try:
        r=Reader(data,1)
        proto        = r.int32()       # [1-4] ProtocolId
        connect_time = r.int64()       # [5-12] connectTime
        version      = r.int32()       # [13-16] client version
        secret       = r.string_i32()  # [17+] secret (int32 len + bytes)
        bend_key     = r.string_i32()  # "game"
    except Exception as ex:
        if DEBUG: log(f"    parse warn: {ex}", Y)

    ok=(version==8 and secret==SECRET)
    log(f"[+] Connect {addr}  ver={version}  connNum={conn_num}  secret={'ok ✓' if ok else repr(secret)}", G if ok else R)

    if not ok:
        log(f"    [REJECT]", R); return


    send_connect_accept(sock, addr, connect_time, conn_num)
    log(f"    ConnectAccept(11б) → {addr}", G)

def on_ping(sock, addr, data):

    if len(data) < 3: return
    seq = struct.unpack_from('<H', data, 1)[0]
    t = int(time.time()*1000)
    w=Writer(); w.byte(PROP_PONG); w.ushort(seq); w.int64(t)
    sock.sendto(w.bytes(), addr)

def on_channeled(sock, addr, data):
    if len(data) < 4: return
    conn_num   = get_conn_num(data[0])
    seq        = struct.unpack_from('<H', data, 1)[0]
    channel_id = data[3]


    send_ack(sock, addr, channel_id, seq, conn_num)

    try:
        r=Reader(data, 4)
        magic=r.int32()  
        if magic!=REQ_MAGIC:
            if DEBUG: log(f"    [data?] magic={magic} {data[:16].hex()}", Y)
            return
        index = r.uint32()
        url   = r.string_i32()   # int32 
        body  = r.string_i32()   # int32 
        result = handle(url, body, addr)

        send_unreliable(sock, addr, make_resp(index, 0, result))
    except Exception as ex:
        log(f"    [ERR] channeled: {ex}", R)
        if DEBUG: log(f"    raw: {data[:32].hex()}", Y)

def on_packet(sock, addr, data):
    if not data: return
    prop = data[0] & 0x1F
    if DEBUG and prop not in (PROP_PING, PROP_PONG, PROP_ACK):
        log(f"  pkt prop={prop} connNum={(data[0]&0x60)>>5} len={len(data)} {data[:16].hex()}", Y)
    if   prop==PROP_CONNECT_REQUEST: on_connect_request(sock,addr,data)
    elif prop==PROP_PING:            on_ping(sock,addr,data)
    elif prop==PROP_CHANNELED:       on_channeled(sock,addr,data)
    elif prop==PROP_DISCONNECT:      log(f"[-] Disconnect {addr}",Y)
    elif prop==PROP_ACK: pass
    else:
        if DEBUG: log(f"  [??] prop={prop}", Y)

def main():
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    sock.bind(("0.0.0.0",PORT)); sock.settimeout(0.5)
    log("╔══════════════════════════════════════════════════════════╗", C)
    log("║                                                          ║", C)
    log("║     MadOut2 Auth Server                                  ║", C)
    log("║          LiteNetLib                                      ║", C)
    log("║                                                          ║", C)
    log("║     By catir1337                                         ║", C)
    log("║     https://github.com/catir1337                         ║", C)
    log("║                                                          ║", C)
    log("╚══════════════════════════════════════════════════════════╝", C)
    while True:
        try:
            data,addr=sock.recvfrom(65535)
            threading.Thread(target=on_packet,args=(sock,addr,data),daemon=True).start()
        except socket.timeout: pass
        except KeyboardInterrupt: log("\nОстановлен.",Y); break
        except Exception as ex: log(f"[ERR] {ex}",R)

if __name__=="__main__": main()