from fastapi import FastAPI, Request
from fastapi.responses import Response

app = FastAPI(title="CMS SOAP Mock")

@app.post("/soap")
async def soap(req: Request):
    body = await req.body()
    # minimal validation (demo)
    resp = f"""<?xml version="1.0"?>
<Envelope>
  <Body>
    <CreateOrderResponse>
      <Status>OK</Status>
    </CreateOrderResponse>
  </Body>
</Envelope>
"""
    return Response(content=resp, media_type="text/xml")