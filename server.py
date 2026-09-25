import os
import json
import asyncio
import websockets

PORT = int(os.environ.get("PORT", 10000))
ROOMS = {}

async def handle_client(websocket):
    room_code = None
    player_name = None
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "join":
                room_code = data.get("room_code")
                room_pass = data.get("room_pass")
                player_name = data.get("player_name", "Giocatore")
                punti = data.get("punti_vittoria", 5)

                if not room_code or not room_pass:
                    await websocket.send(json.dumps({"type": "error", "msg": "Nome stanza e password richiesti."}))
                    await websocket.close()
                    return

                if room_code not in ROOMS:
                    ROOMS[room_code] = {
                        "pass": room_pass,
                        "players": [(websocket, player_name)],
                        "punti": punti,
                        "moves": {},
                        "scores": {player_name: 0}
                    }
                else:
                    r = ROOMS[room_code]
                    if r["pass"] != room_pass:
                        await websocket.send(json.dumps({"type": "error", "msg": "Password stanza errata!"}))
                        await websocket.close()
                        return

                    if len(r["players"]) >= 2:
                        await websocket.send(json.dumps({"type": "error", "msg": "La stanza e' gia' piena!"}))
                        await websocket.close()
                        return

                    r["players"].append((websocket, player_name))
                    r["scores"][player_name] = 0

                    p1_ws, p1_name = r["players"][0]
                    p2_ws, p2_name = r["players"][1]

                    await p1_ws.send(json.dumps({"type": "init", "opponent_name": p2_name, "punti_vittoria": r["punti"]}))
                    await p2_ws.send(json.dumps({"type": "init", "opponent_name": p1_name, "punti_vittoria": r["punti"]}))

            elif msg_type == "move":
                r = ROOMS.get(room_code)
                if r:
                    r["moves"][player_name] = {"dita": data["dita"], "somma": data["somma"]}
                    if len(r["moves"]) == 2:
                        names = list(r["moves"].keys())
                        m1, m2 = r["moves"][names[0]], r["moves"][names[1]]
                        totale = m1["dita"] + m2["dita"]

                        win1, win2 = (m1["somma"] == totale), (m2["somma"] == totale)
                        if win1 and not win2:
                            r["scores"][names[0]] += 1
                            txt = f"Punto a {names[0]}!"
                        elif win2 and not win1:
                            r["scores"][names[1]] += 1
                            txt = f"Punto a {names[1]}!"
                        elif win1 and win2:
                            txt = "Entrambi avete indovinato! Nessun punto."
                        else:
                            txt = "Nessuno ha indovinato!"

                        res = json.dumps({
                            "type": "round_result",
                            "moves": r["moves"],
                            "totale": totale,
                            "scores": r["scores"],
                            "esito_testo": txt
                        })

                        for p_ws, _ in r["players"]:
                            await p_ws.send(res)
                        r["moves"] = {}
    except Exception:
        pass
    finally:
        if room_code in ROOMS:
            del ROOMS[room_code]

async def main():
    async with websockets.serve(handle_client, "0.0.0.0", PORT):
        print(f"Server WebSocket attivo sulla porta {PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())