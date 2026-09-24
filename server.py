import asyncio
import json
import websockets

ROOMS = {}

async def handle_client(websocket):
    current_room = None
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")

            # 1. Creazione Stanza
            if msg_type == "create_room":
                room = data.get("room", "").strip()
                pw = data.get("password", "").strip()
                pname = data.get("player_name", "").strip()
                punti = int(data.get("punti", 5))

                if not room or not pw:
                    await websocket.send(json.dumps({"type": "error", "msg": "Nome stanza e password obbligatori!"}))
                    continue

                if room in ROOMS:
                    await websocket.send(json.dumps({"type": "error", "msg": "Nome stanza già occupato!"}))
                else:
                    ROOMS[room] = {
                        "password": pw,
                        "p1": websocket, "p1_name": pname,
                        "p2": None, "p2_name": None,
                        "punti": punti, "p1_move": None, "p2_move": None,
                        "p1_score": 0, "p2_score": 0
                    }
                    current_room = room
                    await websocket.send(json.dumps({"type": "created", "room": room}))

            # 2. Accesso Stanza
            elif msg_type == "join_room":
                room = data.get("room", "").strip()
                pw = data.get("password", "").strip()
                pname = data.get("player_name", "").strip()

                if room not in ROOMS:
                    await websocket.send(json.dumps({"type": "error", "msg": "Stanza non trovata!"}))
                elif ROOMS[room]["password"] != pw:
                    await websocket.send(json.dumps({"type": "error", "msg": "Password errata!"}))
                elif ROOMS[room]["p2"] is not None:
                    await websocket.send(json.dumps({"type": "error", "msg": "Stanza piena!"}))
                else:
                    ROOMS[room]["p2"] = websocket
                    ROOMS[room]["p2_name"] = pname
                    current_room = room

                    r = ROOMS[room]
                    await r["p1"].send(json.dumps({"type": "start", "role": "p1", "p1_name": r["p1_name"], "p2_name": r["p2_name"], "punti": r["punti"]}))
                    await r["p2"].send(json.dumps({"type": "start", "role": "p2", "p1_name": r["p1_name"], "p2_name": r["p2_name"], "punti": r["punti"]}))

            # 3. Gestione Mosse
            elif msg_type == "move" and current_room in ROOMS:
                r = ROOMS[current_room]
                x, y = data.get("x"), data.get("y")

                if websocket == r["p1"]:
                    r["p1_move"] = (x, y)
                elif websocket == r["p2"]:
                    r["p2_move"] = (x, y)

                if r["p1_move"] is not None and r["p2_move"] is not None:
                    x1, y1 = r["p1_move"]
                    x2, y2 = r["p2_move"]
                    somma = x1 + x2

                    if y1 == somma and y2 != somma:
                        r["p1_score"] += 1
                    elif y2 == somma and y1 != somma:
                        r["p2_score"] += 1

                    punti_obj = r["punti"]
                    game_over, winner = False, None

                    in_spareggio = (r["p1_score"] >= punti_obj - 1) and (r["p2_score"] >= punti_obj - 1)
                    if in_spareggio:
                        if r["p1_score"] - r["p2_score"] >= 2:
                            game_over, winner = True, r["p1_name"]
                        elif r["p2_score"] - r["p1_score"] >= 2:
                            game_over, winner = True, r["p2_name"]
                    else:
                        if r["p1_score"] >= punti_obj:
                            game_over, winner = True, r["p1_name"]
                        elif r["p2_score"] >= punti_obj:
                            game_over, winner = True, r["p2_name"]

                    payload = json.dumps({
                        "type": "round_result",
                        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "somma": somma,
                        "p1_score": r["p1_score"], "p2_score": r["p2_score"],
                        "game_over": game_over, "winner": winner
                    })

                    await r["p1"].send(payload)
                    await r["p2"].send(payload)
                    r["p1_move"], r["p2_move"] = None, None

    except Exception:
        pass
    finally:
        if current_room and current_room in ROOMS:
            r = ROOMS[current_room]
            msg_disc = json.dumps({"type": "disconnected"})
            for ws in (r["p1"], r["p2"]):
                if ws and ws != websocket:
                    try:
                        await ws.send(msg_disc)
                    except Exception:
                        pass
            del ROOMS[current_room]

async def main():
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        print(">>> SERVER ATTIVO SULLA PORTA 8765 <<<")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())