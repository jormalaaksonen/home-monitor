#! /usr/bin/env python3

import logging
import coloredlogs
import configparser
import argparse
import time

from tuya_iot import (
    TuyaOpenAPI,
    AuthType,
    TuyaOpenMQ,
    TuyaDeviceManager,
    TuyaHomeManager,
    TuyaDeviceListener,
    TuyaDevice,
    TuyaTokenInfo,
    TUYA_LOGGER
)

from tuyalinksdk.client import TuyaClient
from tuyalinksdk.console_qrcode import qrcode_generate

connections = {}
devices = {}
states = {}
debug = 0
time_format = '%Y-%m-%d %H:%M:%S'

# ---------------------------------------------------------------------------

def open_tuya_connection(d):
    v = ['endpoint', 'access_id', 'access_key', 'username', 'password']
    for i in v:
        if i not in d:
            print(f'KEY {i} not in configuration for TUYA connection')
            return None
    if debug>0:
        print(f'STARTING TO OPEN tuya connection {d["username"]} {d["endpoint"]}')
    c = {'type': 'tuya'}
    c['openapi'] = TuyaOpenAPI(d['endpoint'], d['access_id'], d['access_key'], AuthType.CUSTOM)
    #            = TuyaOpenAPI(ENDPOINT, ACCESS_ID, ACCESS_KEY, AuthType.SMART_HOME)

    c['openapi'].connect(d['username'], d['password'], "358", "Koti") # , "smartlife"
    c['openmq'] = TuyaOpenMQ(c['openapi'])
    #c['openmq'].start()
    c['devicemanager'] = TuyaDeviceManager(c['openapi'], c['openmq'])

    time.sleep(1)
    
    if debug>0:
        print(f'READY OPENING tuya connection {d["username"]} {d["endpoint"]}')
    
    return c
    
# ---------------------------------------------------------------------------

def open_tuya_client_connection(d):
    global clxxx # should bet rid of this...
    
    def on_connected():
        pass
        #print('Connected.')

    def on_qrcode(url):
        qrcode_generate(url)

    def on_reset(data):
        print('Reset:', data)

    def on_dps(dps):
        print('DataPoints:', dps)
        clxxx.push_dps(dps)

    v = ['product_id', 'uuid', 'authkey']
    for i in v:
        if i not in d:
            print(f'KEY {i} not in configuration for TUYA CLIENT connection')
            return None
    if debug>0:
        print(f'STARTING TO OPEN tuya client connection {d["product_id"]}')
    c = {'type': 'tuya-client'}
    c['client'] = TuyaClient(productid='dckfipsgz4kkfxta',
                        uuid='uuidfa1a7dd4c6d90043',
                        authkey='Fk1tP2PeG1lG1YVZ6pEyAgkcFfDMjCJg')

    c['client'].on_connected = on_connected
    c['client'].on_qrcode = on_qrcode
    c['client'].on_reset = on_reset
    c['client'].on_dps = on_dps
    c['client'].connect()
    c['client'].loop_start()
    
    time.sleep(1)

    clxxx = c['client']
    
    if debug>0:
        print(f'READY OPENING tuya client connection {d["product_id"]}')
    
    return c
    
# ---------------------------------------------------------------------------

def ensure_connection(d):
    t = d.get('type', '')
    if '.connection' not in d:
        if t=='tuya':
            k = f'tuya-{d["endpoint"]}-{d["username"]}'
            if k not in connections:
                connections[k] = open_tuya_connection(d)
                d['.connection'] = k
        elif t=='tuya-client':
            k = f'tuya-client-{d["product_id"]}'
            if k not in connections:
                connections[k] = open_tuya_client_connection(d)
                d['.connection'] = k
        else:
            print(f'No rule for making a conncetion for "{d[".name"]}" type={t} known.')
        
# ---------------------------------------------------------------------------

def read_tuya_device(d):
    if debug>0:
        print(f'READING TUYA DEVICE {d} ==> {connections[d[".connection"]]}')

    c = connections[d['.connection']]
    m = c['devicemanager'].get_device_status(d['device_id'])
    #print(m)
    if not m.get('success', False):
        print(f'READING DEVICE {d} FAILED: {m}')
        return

    k = d.get('code', '').split(',')
    if len(k)==1 and k[0]=='':
        k = []
    s = set(k)

    a = {}
    for i in m.get('result', []):
        for j in k:
            if i.get('code', '')==j:
                a[j] = i.get('value', '')
                s.remove(j)
    for j in s:
        a[j] = None

    return a
                
# ---------------------------------------------------------------------------

def read_tuya_client(d):
    if debug>0:
        print(f'READING TUYA CLIENT {d} ==> {connections[d[".connection"]]}')

    if '.i' not in d:
        d['.i'] = 0
        
    c = connections[d['.connection']]

    msg = [ 'hello', 'world', 'here', 'we'' go', 'again' ]
    #print('pushing', flush=True)
    a = {'101': msg[d['.i']%len(msg)], '102': d['.i']%10, '103': 37}
    c['client'].push_dps(a)
    #print('pushed', flush=True)
    d['.i'] += 1

    return a
                
# ---------------------------------------------------------------------------

def read_device(d):
    if '.connection' not  in d:
        print(f'NO CONNECTION IN {d[".name"]}')
        return {}
    if connections[d['.connection']] is None:
        print(f'None CONNECTION IN {d[".name"]}')
        return {}
    if debug>0:
        print(f'READING DEVICE {d} ==> {connections[d[".connection"]]}')

    t = connections[d['.connection']].get('type', '')

    if t=='tuya':
        return read_tuya_device(d)

    if t=='tuya-client':
        return read_tuya_client(d)

    print(f'NO READING/WRITING defined for "{d[".name"]}" type={t} known.')
    
    return {}
    
# ---------------------------------------------------------------------------

def time_str(t):
    return time.strftime(time_format, t)

# ---------------------------------------------------------------------------

def state_string(s):
    a = [ f'{time_str(i["start"])} –> {time_str(i["end"])} = {i["state"]}' for i in s ]
    return ', '.join(a)
    
# ---------------------------------------------------------------------------

def track_device(d):
    m = read_device(d)
    t = d['.previous']
    s = time_str(t)
    print(f'{s} {d[".name"]} => {m}')
    for i,j in m.items():
        k = d['.name']+' '+i
        if k not in states:
            states[k] = []
        if len(states[k])==0 or states[k][-1]['state']!=j:
            states[k].append({'state': j, 'start':t, 'end':t})
            print(k, ': ', state_string(states[k]))
        states[k][-1]['end'] = t
    
# ---------------------------------------------------------------------------

def configread(config, s):
    a = {}
    for k in config[s].keys():
        if k=='baseclass':
            a = configread(config, config[s][k])
    for k in config[s].keys():
        if k!='baseclass':
            a[k] = config[s][k]

    a['.name'] = s

    return a

# ---------------------------------------------------------------------------

def config2devices(config):
    global devices
    devices = {}
    for i in config.sections():
        if len(i)<3 or i[0]!='=' or i[-1]!='=':
            devices[i] = configread(config, i)
    
# ---------------------------------------------------------------------------
    
if __name__ == '__main__':
    #test()
    #exit(0)

    parser = argparse.ArgumentParser(
        prog='ProgramName',
        description='What the program does',
        epilog='Text at the bottom of help')
    parser.add_argument('-v', '--verbose',
                        action='store_true')
    args = parser.parse_args()

    # TUYA_LOGGER.setLevel(logging.DEBUG)
    # coloredlogs.install(level='DEBUG')

    config = configparser.ConfigParser()
    config.read('config')
    config2devices(config)
    if debug>0:
        print(devices)

    while True:
        hit = False
        now = time.localtime()
        #print(now)
        
        for _,i in devices.items():
            l = i.get('.previous', None)
            v = float(i.get('interval', 60))
            if l is None or time.mktime(now)-time.mktime(l)>=v:
                i['.previous'] = now
                ensure_connection(i)
                track_device(i)
                hit = True

        if not hit:
            print(time_str(now))
            
        time.sleep(1)
        
