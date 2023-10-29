import wifi
import socketpool

import adafruit_ntp

from native_http_server import AppServer


class Platform:
    def __init__(self, app):
        self._server = None
        self._app = app
        self._ntp = None

    def wifi_connect(self):
        if not wifi.radio.connected:
            ssid = os.getenv("wifi_ssid")
            password = os.getenv("wifi_password")

            if ssid is None or password is None:
                print("wifi_ssid or wifi_password not set in secrets.toml")
                return

            try:
                wifi.radio.connect(ssid, password)
            except ConnectionError:
                print("wifi failure")
                print("scanning...")
                for access_point in self.esp.scan_networks():
                    print(
                        f'\t{access_point["ssid"].decode()}\t\tRSSI: {access_point["rssi"]}'
                    )

                    time.sleep(5)
                    microcontroller.reset()

                print(
                    "MAC address ",
                    ":".join(
                        "%02x" % b
                        for b in self.esp.MAC_address_actual  # pylint: disable=consider-using-f-string,line-too-long
                    ),
                )
                return

        pool = socketpool.SocketPool(wifi.radio)
        self._ntp = adafruit_ntp.NTP(pool, tz_offset=0)

    @property
    def wifi_ip_address(self):
        return wifi.radio.ipv4_address

    @property
    def native(self):
        return True

    def ntp_sync(self):
        if self._ntp is not None:
            return self._ntp.datetime

        return None

    def syslog(self):
        pass

    def start_server(self):
        self._server = AppServer(self._app)
        self._server.start()

    @property
    def server(self):
        return self._server

    def loop(self):
        self._server.loop()
