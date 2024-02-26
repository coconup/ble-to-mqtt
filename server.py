import os
import configparser
import logging
import json
import sys
import time
import math

from aiohttp import web

sys.path.append('./lib/batmon-ha')
sys.path.append('./lib/renogy-bt')

import bmslib.models.ant
import bmslib.models.daly
import bmslib.models.dummy
import bmslib.models.jbd
import bmslib.models.jikong
import bmslib.models.sok
import bmslib.models.supervolt
import bmslib.models.victron

import bmslib.bt

from renogybt import InverterClient, RoverClient, RoverHistoryClient, BatteryClient, DataLogger, Utils

mqtt_config = configparser.ConfigParser()
mqtt_config['mqtt'] = {
    'enabled': True,
    'server': os.environ.get('MQTT_HOST'),
    'port': os.environ.get('MQTT_PORT', '1883'),
    'topic': os.environ.get('MQTT_TOPIC'),
    'user': os.environ.get('MQTT_USER', ''),
    'password': os.environ.get('MQTT_PASSWORD', '')
}

data_logger: DataLogger = DataLogger(mqtt_config)

def restart_bluetooth():
    logging.info('Restarting bluetooth')
    bmslib.bt.bt_power(False)
    time.sleep(1)
    bmslib.bt.bt_power(True)
    time.sleep(2)

async def on_startup(app):
    restart_bluetooth()

batmon_bms_registry = dict(
    daly      = bmslib.models.daly.DalyBt,
    jbd       = bmslib.models.jbd.JbdBt,
    jk        = bmslib.models.jikong.JKBt,
    ant       = bmslib.models.ant.AntBt,
    victron   = bmslib.models.victron.SmartShuntBt,
    supervolt = bmslib.models.supervolt.SuperVoltBt,
    sok       = bmslib.models.sok.SokBt
)

def filter_data(data):
    return {key: value for key, value in data.items() if not (isinstance(value, float) and math.isnan(value))}

def enrich_data(data, request):
    device_id = request.query.get('device_id')
    device_type = request.query.get('device_type')
    data['device_id'] = device_id
    data['device_type'] = device_type
    return data

def make_renogy_data_received_callback(request):
    def callback(client, data):
        logging.info(f'returning {data.__class__.__name__}')
        data_logger.log_mqtt(json_data=json.dumps(enrich_data(filter_data(data), request)))
        try:
            client.device.disconnect()
        except Exception as e:
            renogy_on_connect_fail(client, e)
    return callback

def renogy_stop_service(self):
    if self.poll_timer is not None and self.poll_timer.is_alive():
        self.poll_timer.cancel()
    if self.poll_timer is not None: self.read_timer.cancel()
    self.manager.stop()
    # os._exit(os.EX_OK)

def renogy_on_connect_fail(self, error):
    self.__stop_service()
    if error != 'Disconnected':
        logging.error(f"Connection failed: {error}")
        renogy_stop_service(self)
        os._exit(os.EX_OK)

RoverClient.__stop_service = renogy_stop_service

async def batmon_fetch_bms_data(bms, request):
    data = {}
    await bms.connect()
    voltages = await bms.fetch_voltages()
    sample = await bms.fetch()
    data['voltages'] = voltages
    data['voltage'] = sample.voltage
    data['current'] = sample.current
    data['power'] = sample.power
    data['balance_current'] = sample.balance_current
    data['charge'] = sample.charge
    data['capacity'] = sample.capacity
    data['soc'] = sample.soc
    data['cycle_capacity'] = sample.cycle_capacity
    data['num_cycles'] = sample.num_cycles
    data['temperatures'] = sample.temperatures
    data['mos_temperature'] = sample.mos_temperature
    data['switches'] = sample.switches
    data['uptime'] = sample.uptime
    data['timestamp'] = sample.timestamp
    data_logger.log_mqtt(json_data=json.dumps(enrich_data(filter_data(data), request)))
    await bms.disconnect()

async def get_info(request):
    try:
        # Get request parameters
        mac_address = request.query.get('mac_address')
        adapter = request.query.get('adapter')
        device_subtype = request.query.get('device_subtype')
        mqtt_topic = request.query.get('mqtt_topic')
        pin = request.query.get('pin')
        debug = request.query.get('debug')

        if debug:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        if adapter == 'renogy':
            if device_subtype == 'rover':
                renogy_config = configparser.ConfigParser()
                renogy_config['device'] = {"adapter": "hci0", "alias": "", "mac_addr": mac_address, "type": device_subtype, "device_id": "255"}
                renogy_config['data'] = {"temperature_unit": "C", "fields": ""}
                renogy_config['remote_logging'] = {}
                renogy_config['mqtt'] = {}
                renogy_config['pvoutput'] = {}
                client = RoverClient(renogy_config, make_renogy_data_received_callback(request), renogy_on_connect_fail)
                client.connect()
        elif adapter == 'batmon':
            bms_class = batmon_bms_registry.get(device_subtype)
            bms = bms_class(
                mac_address,
                name=mqtt_topic,
                verbose_log=debug,
                psk=pin
            )
            try:
                await batmon_fetch_bms_data(bms, request)
            except Exception as e:
                await bms.disconnect()
                restart_bluetooth()

        return web.json_response({"success": True})
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)})

app = web.Application()
app.router.add_get('/get_info', get_info)

if __name__ == '__main__':
    logging.info('starting server')
    app.on_startup.append(on_startup)
    web.run_app(app, port=5000)