import os
import json
import socket
import threading

PORT = int(os.environ.get("PORT", 10000))
rooms = {}  # { room_code: { "pass": str, "players": [conn1, conn2], "names": [name1, name2], "punti": int, "moves": {}, "scores": {} } }

def send_json(conn, payload):
    try:
        conn.sendall((json.dumps(payload) + "\n").encode('utf-8'))
    except Exception:
        pass

def handle_client(conn, addr):
    room_code = None
    player_name = None

    try:
        buf = bytearray()
        while True:
            c = conn.recv(1)
            if not c or c == b'\n':
                break
            buf.extend(c)

        if not buf:
            conn.close()
            return

        data = json.loads(buf.decode('utf-8'))
        if data.get("type") == "join":
            room_code = data.get("room_code")
            room_pass = data.get("room_pass")
            player_name = data.get("player_name", "Giocatore")
            punti = data.get("punti_vittoria", 5)

            if not room_code or not room_pass:
                send_json(conn, {"type": "error", "msg": "Nome stanza e password richiesti."})
                conn.close()
                return

            if room_code not in rooms:
                # Crea nuova stanza privata
                rooms[room_code] = {
                    "pass": room_pass,
                    "players": [(conn, player_name)],
                    "punti": punti,
                    "moves": {},
                    "scores": {player_name: 0}
                }
            else:
                # Verifica password e capienza
                r = rooms[room_code]
                if r["pass"] != room_pass:
                    send_json(conn, {"type": "error", "msg": "Password stanza errata!"})
                    conn.close()
                    return

                if len(r["players"]) >= 2:
                    send_json(conn, {"type": "error", "msg": "La stanza e' gia' piena!"})
                    conn.close()
                    return

                r["players"].append((conn, player_name))
                r["scores"][player_name] = 0

                # Entrambi i giocatori sono connessi -> Avvio partita
                p1_conn, p1_name = r["players"][0]
                p2_conn, p2_name = r["players"][1]

                send_json(p1_conn, {"type": "init", "opponent_name": p2_name, "punti_vittoria": r["punti"]})
                send_json(p2_conn, {"type": "init", "opponent_name": p1_name, "punti_vittoria": r["punti"]})

            # Loop principale della partita per questo client
            while True:
                buf = bytearray()
                while True:
                    c = conn.recv(1)
                    if not c or c == b'\n':
                        break
                    buf.extend(c)

                if not buf:
                    break

                msg = json.loads(buf.decode('utf-8'))
                if msg.get("type") == "move":
                    r = rooms.get(room_code)
                    if not r:
                        break

                    r["moves"][player_name] = {"dita": msg["dita"], "somma": msg["somma"]}

                    # Se entrambi hanno inviato la mossa, calcola l'esito
                    if len(r["moves"]) == 2:
                        names = list(r["moves"].keys())
                        m1 = r["moves"][names[0]]
                        m2 = r["moves"][names[1]]
                        totale = m1["dita"] + m2["dita"]

                        win1 = (m1["somma"] == totale)
                        win2 = (m2["somma"] == totale)

                        if win1 and not win2:
                            r["scores"][names[0]] += 1
                            txt = f"Punto a {names[0]}!"
                        elif win2 and not win1:
                            r["scores"][names[1]] += 1
                            txt = f"Punto a {names[1]}!"
                        elif win1 and win2:
                            txt = "Entrambi hanno indovinato! Nessun punto."
                        else:
                            txt = "Nessuno ha indovinato!"

                        res = {
                            "type": "round_result",
                            "moves": r["moves"],
                            "totale": totale,
                            "scores": r["scores"],
                            "esito_testo": txt
                        }

                        for p_conn, _ in r["players"]:
                            send_json(p_conn, res)

                        r["moves"] = {}

    except Exception:
        pass
    finally:
        conn.close()
        if room_code in rooms:
            del rooms[room_code]

def start():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", PORT))
    server.listen(10)
    print(f"Server Morra in ascolto sulla porta {PORT}...")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start()