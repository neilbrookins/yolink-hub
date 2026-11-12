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
mod('homeassistant.config_entries', ConfigEntry=ConfigEntry)
mod('homeassistant.core', HomeAssistant=object, callback=lambda f:f)
class DR:
    def async_get_device(s, identifiers): return types.SimpleNamespace(id='d', sw_version='1310')
    def async_update_device(s, i, sw_version): print('   device sw_version ->', sw_version)
mod('homeassistant.helpers.device_registry', async_get=lambda h: DR(), DeviceInfo=dict)
class DUC:
    def __class_getitem__(c, i): return c
    def __init__(s, hass, logger, config_entry, name, update_interval): s.hass=hass; s.config_entry=config_entry; s.data=None
class CE:
    def __class_getitem__(c, i): return c
    def __init__(s, coordinator): s.coordinator=coordinator
    available=True
mod('homeassistant.helpers.update_coordinator', DataUpdateCoordinator=DUC, CoordinatorEntity=CE)
@dataclasses.dataclass(frozen=True, kw_only=True)
class ED:
    key:str; device_class:object=None; entity_category:object=None; options:object=None
class SDC(enum.Enum): ENUM='enum'
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
asyncio.run(main())
