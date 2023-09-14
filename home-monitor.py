#! /usr/bin/env python3

import logging
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

connections = {}
devices = {}
debug = 0

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

def ensure_connection(d):
    if '.connection' not in d:
        if d.get('type', '')=='tuya':
            k = f'tuya-{d["endpoint"]}-{d["username"]}'
            if k not in connections:
                connections[k] = open_tuya_connection(d)
                d['.connection'] = k
        
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

def read_device(d):
    if '.connection' not  in d:
        print(f'NO CONNECTION IN {d[".name"]}')
        return {}
    if debug>0:
        print(f'READING DEVICE {d} ==> {connections[d[".connection"]]}')

    if connections[d['.connection']].get('type', '')=='tuya':
        return read_tuya_device(d)

    return {}
    
# ---------------------------------------------------------------------------

def track_device(d):
    m = read_device(d)
    print(f'{time.strftime("%Y%m%d %H:%M:%S")} {d[".name"]} => {m}')
    
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
    parser = argparse.ArgumentParser(
        prog='ProgramName',
        description='What the program does',
        epilog='Text at the bottom of help')
    parser.add_argument('-v', '--verbose',
                        action='store_true')
    args = parser.parse_args()

    # TUYA_LOGGER.setLevel(logging.DEBUG)

    config = configparser.ConfigParser()
    config.read('config')
    config2devices(config)
    if debug>0:
        print(devices)

    for t in range(300):
        for _,i in devices.items():
            ensure_connection(i)
            track_device(i)
        time.sleep(1)
        
