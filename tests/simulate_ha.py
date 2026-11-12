"""Run the coordinator and entities with stubbed Home Assistant, against the captures.

Run with: python3 tests/simulate_ha.py
"""
import sys, types, asyncio, json, pathlib, dataclasses, enum
R=pathlib.Path(__file__).resolve().parents[1]
def mod(name, **kw):
    m=types.ModuleType(name); m.__dict__.update(kw); sys.modules[name]=m; return m
# aiohttp
class ClientError(Exception): pass
mod('aiohttp', ClientError=ClientError, ClientTimeout=lambda **k: None, ClientSession=object)
# icmplib
class SocketPermissionError(Exception): pass
PING={'alive':True}
async def async_ping(host, **k):
    return types.SimpleNamespace(is_alive=PING['alive'])
mod('icmplib', SocketPermissionError=SocketPermissionError, async_ping=async_ping)
# homeassistant stubs
mod('homeassistant'); mod('homeassistant.helpers'); mod('homeassistant.components')
class ConfigEntry:
    def __init__(s,data,options): s.data=data; s.options=options; s.entry_id='e1'
    def async_on_unload(s, f): pass
    def async_create_background_task(s, hass, coro, name):
        t=asyncio.get_running_loop().create_task(coro); TASKS.append(t); return t
mod('homeassistant.config_entries', ConfigEntry=ConfigEntry)
mod('homeassistant.core', HomeAssistant=object, callback=lambda f:f)
class DR:
    def async_get_device(s, identifiers): return types.SimpleNamespace(id='d', sw_version='1310')
    def async_update_device(s, i, sw_version): print('   device sw_version ->', sw_version)
mod('homeassistant.helpers.device_registry', async_get=lambda h: DR(), DeviceInfo=dict,
    async_entries_for_config_entry=lambda reg, entry_id: [types.SimpleNamespace(id='d', sw_version='1310')])
class DUC:
    def __class_getitem__(c, i): return c
    def __init__(s, hass, logger, config_entry, name, update_interval): s.hass=hass; s.config_entry=config_entry; s.data=None
    def async_set_updated_data(s, data): s.data=data; print('   (shown at once) status=', data.status)
    async def async_refresh(s): s.data=await s._async_update_data()
class CE:
    def __class_getitem__(c, i): return c
    def __init__(s, coordinator): s.coordinator=coordinator
    available=True
    def _handle_coordinator_update(s): pass
import datetime as _dt
TIMERS=[]; TASKS=[]
mod('homeassistant.helpers.event', async_track_time_interval=lambda hass, cb, interval: TIMERS.append((cb, interval)) or (lambda: None))
NOW=[_dt.datetime(2026,11,12,19,0,tzinfo=_dt.timezone.utc)]
mod('homeassistant.util'); mod('homeassistant.util.dt', utcnow=lambda: NOW[0], parse_datetime=_dt.datetime.fromisoformat)
class RestoreEntity:
    _last=None
    async def async_added_to_hass(s): pass
    async def async_get_last_state(s): return s._last
mod('homeassistant.helpers.restore_state', RestoreEntity=RestoreEntity)
mod('homeassistant.helpers.update_coordinator', DataUpdateCoordinator=DUC, CoordinatorEntity=CE)
@dataclasses.dataclass(frozen=True, kw_only=True)
class ED:
    key:str; device_class:object=None; entity_category:object=None; options:object=None
class SDC(enum.Enum): ENUM='enum'; TIMESTAMP='timestamp'
class BDC(enum.Enum): CONNECTIVITY='connectivity'; PROBLEM='problem'
mod('homeassistant.components.sensor', SensorDeviceClass=SDC, SensorEntity=object, SensorEntityDescription=ED)
mod('homeassistant.components.binary_sensor', BinarySensorDeviceClass=BDC, BinarySensorEntity=object, BinarySensorEntityDescription=ED)
class EC(enum.Enum): DIAGNOSTIC='diagnostic'
mod('homeassistant.const', EntityCategory=EC, Platform=None)
mod('homeassistant.helpers.entity_platform', AddEntitiesCallback=object)
# load package
pkg=mod('custom_components'); pkg.__path__=[str(R/'custom_components')]
import importlib
yh=types.ModuleType('custom_components.yolink_hub'); yh.__path__=[str(R/'custom_components/yolink_hub')]; sys.modules['custom_components.yolink_hub']=yh
coordm=importlib.import_module('custom_components.yolink_hub.coordinator')
sensorm=importlib.import_module('custom_components.yolink_hub.sensor')
binm=importlib.import_module('custom_components.yolink_hub.binary_sensor')
apim=importlib.import_module('custom_components.yolink_hub.api')

class FakeApi:
    def __init__(s, replies): s.replies=list(replies); s.calls=0; s.invalidated=0
    async def get_state(s,t,i,tok):
        s.calls+=1; r=s.replies.pop(0)
        if isinstance(r,Exception): raise r
        return r
    def invalidate_token(s): s.invalidated+=1
    async def device_list(s): return [{'deviceId':'hub1','token':'NEWTOKEN'}]
updates=[]
hass=types.SimpleNamespace(config_entries=types.SimpleNamespace(async_update_entry=lambda e,data: updates.append(data['hub_token'])))
fx=lambda n: json.loads((R/'tests/fixtures'/f'{n}.json').read_text())
def show(c):
    d=c.data
    ents=[sensorm.HubSensor(c,x) for x in sensorm.DESCRIPTIONS]+[binm.HubBinarySensor(c,x) for x in binm.DESCRIPTIONS]
    out=[]
    for e in ents:
        k=e.entity_description.key
        if not e.available: out.append(f'{k}=unavailable'); continue
        v=e.native_value if hasattr(e,'native_value') else ('on' if e.is_on else 'off')
        out.append(f'{k}={v}')
    print('   '+', '.join(out))
    if d.review_reasons: print('   REVIEW:', d.review_reasons)
async def run(label, replies, ping=True, host='192.168.0.250'):
    PING['alive']=ping
    entry=ConfigEntry({'hub_id':'hub1','hub_type':'Hub','hub_token':'T','hub_name':'Pro Hub'},{'local_host':host,'scan_interval':60})
    c=coordm.YoLinkHubCoordinator(hass, entry, FakeApi(replies))
    await c.async_start_pinging()
    c.data=await c._async_update_data()
    print(f'{label}: status={c.data.status}'); show(c); return c
async def main():
    await run('Normal', [fx('normal')])
    await run('AC unplugged', [fx('ac_unplugged')])
    await run('AC restored', [fx('ac_restored')])
    await run('Ethernet unplugged (ping fails)', [fx('ethernet_unplugged')], ping=False)
    await run('Internet down, hub answers ping', [apim.YoLinkCloudError('timeout')], ping=True)
    await run('Everything down', [apim.YoLinkCloudError('timeout')], ping=False)
    await run('Bad credentials', [apim.YoLinkAuthError('rejected')])
    c=await run('Unknown code then OK after token refresh', [{'code':'010104','desc':'Token is expired','data':{}}, fx('normal')])
    print('   hub token saved:', updates)
    await run('Unknown code persists', [{'code':'999999','desc':'Mystery','data':{}}]*2)
    bad=fx('normal'); bad['data']['other']['power']['batteryState']=4
    await run('Battery code 4', [bad])
    await run('No local address set', [fx('normal')], host='')
    print('--- Ping changes between cloud checks: cloud asked until it agrees ---')
    _sleep=asyncio.sleep
    coordm.asyncio.sleep=lambda t, *a, **k: _sleep(0)   # no real waiting in the test
    async def change(c, alive):
        PING['alive']=alive; await cb(None)
        for t in list(TASKS): await t
        TASKS.clear()
    TIMERS.clear()
    reasons=[]
    c=await run('Before', [fx('normal'),
        fx('normal'), fx('ethernet_unplugged'),                       # ping fails: cloud lags once, then agrees
        fx('ethernet_unplugged'), fx('ethernet_unplugged'), fx('normal')])  # recovers: hub still reconnecting twice
    _orig=c._async_update_data
    async def logged():
        d=await _orig(); reasons.append((d.cloud_check_reason, d.status)); return d
    c._async_update_data=logged
    cb, interval = TIMERS[-1]
    print('   ping timer every', interval)
    await change(c, False)
    print('   after ping failed:', reasons); assert reasons==[('ping failed','online_no_ping'),('ping failed, follow-up','offline')]
    reasons.clear(); await cb(None); assert reasons==[]          # still failing: no extra calls
    await change(c, True)
    print('   after ping recovered:', reasons)
    assert reasons==[('ping recovered','offline_cloud_lan_ok'),('ping recovered, follow-up','offline_cloud_lan_ok'),('ping recovered, follow-up','online')]
    assert c.api.calls==6
    print('PING-TRIGGER TEST PASSED')
    print('--- Battery state since ---')
    import datetime as dtm
    def at(m): NOW[0]=dtm.datetime(2026,11,12,19,m,tzinfo=dtm.timezone.utc)
    async def poll(c, e, reply):
        c.api.replies.append(reply); c.data=await c._async_update_data(); e._handle_coordinator_update()
        return (e.native_value.strftime('%H:%M') if e.available else 'unavailable', e.extra_state_attributes)
    TIMERS.clear(); at(0)
    c=await run('Start', [fx('normal')])
    e=sensorm.BatterySinceSensor(c); await e.async_added_to_hass()
    print('   first seen standby :', (e.native_value.strftime('%H:%M'), e.extra_state_attributes))
    assert e.extra_state_attributes=={'battery_state':'standby','exact_start':False}
    at(5); r=await poll(c,e,fx('normal')); assert r[0]=='19:00'
    at(10); r=await poll(c,e,fx('ac_unplugged')); print('   AC unplugged       :', r); assert r==('19:10',{'battery_state':'supply','exact_start':True})
    at(20); r=await poll(c,e,fx('ethernet_unplugged')); print('   hub offline        :', r); assert r[0]=='unavailable'
    at(25); r=await poll(c,e,fx('ac_unplugged')); print('   back, still supply :', r); assert r==('19:10',{'battery_state':'supply','exact_start':True})
    at(40); r=await poll(c,e,fx('ac_restored')); print('   AC restored        :', r); assert r==('19:40',{'battery_state':'charging','exact_start':True})
    # Home Assistant restarts: restored, same state -> keeps its start
    at(50); c2=await run('After restart', [fx('ac_restored')])
    e2=sensorm.BatterySinceSensor(c2); e2._last=types.SimpleNamespace(state='2026-11-12T19:40:00+00:00', attributes={'battery_state':'charging','exact_start':True})
    await e2.async_added_to_hass(); print('   restored, same     :', (e2.native_value.strftime('%H:%M'), e2.extra_state_attributes))
    assert e2.native_value.strftime('%H:%M')=='19:40' and e2.extra_state_attributes['exact_start'] is True
    # restart where the state changed while Home Assistant was down -> not exact
    c3=await run('After restart, changed', [fx('normal')])
    e3=sensorm.BatterySinceSensor(c3); e3._last=e2._last
    await e3.async_added_to_hass(); print('   restored, changed  :', (e3.native_value.strftime('%H:%M'), e3.extra_state_attributes))
    assert e3.extra_state_attributes=={'battery_state':'standby','exact_start':False}
    print('BATTERY-SINCE TEST PASSED')
    print('--- Several hubs on one account ---')
    class Resp:
        def __init__(s, status, body): s.status=status; s.body=body
        async def json(s, content_type=None): return s.body
        async def __aenter__(s): return s
        async def __aexit__(s, *a): return False
    class YoLinkCloud:
        # Issues numbered tokens; only the newest is accepted (worst case: a new token replaces the old)
        def __init__(s): s.issued=0; s.calls=[]
        def post(s, url, data=None, json=None, headers=None, timeout=None):
            if url.endswith('/token'):
                s.issued+=1; return Resp(200, {'access_token': f't{s.issued}', 'expires_in': 7200})
            tok=headers['Authorization'].split()[-1]; s.calls.append((json['targetDevice'], tok))
            if tok != f't{s.issued}': return Resp(401, {})
            return Resp(200, {'code':'000000','data':{'online':True}})
    cloud=YoLinkCloud()
    shared=apim.YoLinkApi(cloud,'uaid','secret')
    for hub in ('hubA','hubB','hubA','hubB'):
        r=await shared.get_state('Hub', hub, 'x'); assert r['code']=='000000'
    print('   shared client: 4 polls of 2 hubs used', cloud.issued, 'token request(s)'); assert cloud.issued==1
    # A second client (e.g. the setup form) gets its own token, replacing the first:
    other=apim.YoLinkApi(cloud,'uaid','secret'); await other.get_state('Hub','hubC','x')
    r=await shared.get_state('Hub','hubA','x'); assert r['code']=='000000'
    print('   after another client replaced the token: rejected once, fresh token, success; calls =', cloud.calls[-2:])
    assert cloud.calls[-2][1]=='t1' and cloud.calls[-1][1]=='t3'
    print('MULTI-HUB TEST PASSED')
asyncio.run(main())
