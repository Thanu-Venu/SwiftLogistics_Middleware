from fastapi import FastAPI, Request
from datetime import datetime, timezone

app = FastAPI()

LAST = {
    "seen_at": None,
    "order_id": None,
    "client_id": None,
    "request_xml": None,
    "response_xml": None,
}

@app.post("/soap")
async def soap(request: Request):
    xml = (await request.body()).decode("utf-8", errors="ignore")

    # very simple extract (optional)
    def extract(tag: str):
      start = xml.find(f"<{tag}>")
      end = xml.find(f"</{tag}>")
      if start == -1 or end == -1: return None
      start += len(tag) + 2
      return xml[start:end].strip()

    order_id = extract("OrderId")
    client_id = extract("ClientId")

    resp = """<?xml version="1.0"?>
<Envelope>
  <Body>
    <CreateOrderResponse>
      <Status>OK</Status>
    </CreateOrderResponse>
  </Body>
</Envelope>
"""

    LAST.update({
        "seen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "order_id": order_id,
        "client_id": client_id,
        "request_xml": xml,
        "response_xml": resp,
    })

    return resp

@app.get("/last")
def last():
    return LAST