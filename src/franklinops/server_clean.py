from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

try:
    from src.spokes.core_ui import generate_core_home_page, generate_loop_page
except:
    def generate_core_home_page():
        return <h1>FranklinOps</h1>
    def generate_loop_page():
        return <h1>Loop</h1>

try:
    from src.spokes.construction import construction_dashboard, pay_app_tracker
    from src.spokes.sales import scan_sales_pipeline, rank_opportunities
    from src.spokes.finance import ap_intake_run, ar_aging_report
except:
    construction_dashboard = lambda x: {}
    pay_app_tracker = lambda x: {}
    scan_sales_pipeline = lambda x: {}
    rank_opportunities = lambda x: {}
    ap_intake_run = lambda x: {}
    ar_aging_report = lambda x: {}

app = FastAPI()

@app.get(/health)
async def health():
    return {status: healthy}

@app.get(/api/status)
async def status():
    return {status: running}

@app.get(/, response_class=HTMLResponse)
async def root():
    return <script>location.href='/ui'</script>

@app.get(/ui, response_class=HTMLResponse)
async def home():
    return generate_core_home_page()

@app.get(/ui/loop, response_class=HTMLResponse)
async def loop():
    return generate_loop_page()

@app.get(/api/construction/dashboard)
async def c_dash():
    return construction_dashboard({})

@app.get(/api/construction/pay-apps)
async def c_pay():
    return pay_app_tracker({})

@app.get(/api/sales/pipeline)
async def s_pipe():
    return scan_sales_pipeline({})

@app.get(/api/sales/opportunities)
async def s_opps():
    return rank_opportunities({})

@app.get(/api/finance/ap-intake)
async def f_ap():
    return ap_intake_run({})

@app.get(/api/finance/ar-aging)
async def f_ar():
    return ar_aging_report({})

class Req(BaseModel):
    tenant_id: str = default

@app.post(/api/loop/run)
async def loop_run(r: Req):
    import uuid
    return {trace_id: str(uuid.uuid4())}

@app.get(/api/loop/status)
async def loop_stat():
    return {status: ready}